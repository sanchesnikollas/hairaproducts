# src/pipeline/coverage_engine.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.models import ProductExtraction, GenderTarget, ExtractionMethod, QAResult, QAStatus
from src.core.field_validator import is_real_usage_instructions
from src.core.gold_gate import evaluate_gold
from src.core.qa_gate import run_product_qa
from src.core.taxonomy import normalize_product_type, normalize_category, detect_gender_target, is_hair_relevant_by_keywords
from src.discovery.url_classifier import classify_url, URLType
from src.extraction.deterministic import extract_product_deterministic
from src.extraction.inci_extractor import extract_and_validate_inci
from src.pipeline.report_generator import BrandReport, generate_coverage_stats
from src.storage.repository import ProductRepository

logger = logging.getLogger(__name__)

STOP_THE_LINE_THRESHOLD = 0.50


def _benefits_to_list(raw: str | None) -> list[str] | None:
    """Convert a benefits text blob (from section_classifier) into a list of bullets.

    Splits on bullets, line breaks, semicolons, and commas-as-list (with min length).
    Returns None when no usable content remains.
    """
    if not raw:
        return None
    import re as _re
    parts = _re.split(r"[\n\r●•·;]+|(?<=\w),(?=\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇa-z])", raw)
    bullets = [p.strip(" -–•\t") for p in parts if p and p.strip()]
    bullets = [b for b in bullets if len(b) >= 8 and len(b) <= 300]
    return bullets or ([raw.strip()] if raw.strip() else None)


class CoverageEngine:
    def __init__(self, session: Session, browser=None, llm_client=None):
        self._session = session
        self._repo = ProductRepository(session)
        self._browser = browser
        self._llm_client = llm_client

    def process_brand(
        self,
        brand_slug: str,
        blueprint: dict,
        discovered_urls: list[dict],
    ) -> BrandReport:
        report = BrandReport(brand_slug=brand_slug)
        allowed_domains = blueprint.get("allowed_domains", [])
        extraction_config = blueprint.get("extraction", {})
        inci_selectors = extraction_config.get("inci_selectors", [])
        name_selectors = extraction_config.get("name_selectors", [])
        image_selectors = extraction_config.get("image_selectors", [])
        price_selectors = extraction_config.get("price_selectors", [])
        description_selectors = extraction_config.get("description_selectors", [])
        section_label_map = extraction_config.get("section_label_map")

        report.discovered_total = len(discovered_urls)

        # Classify URLs
        product_url_pattern = blueprint.get("discovery", {}).get("product_url_pattern")
        hair_urls = []
        for url_info in discovered_urls:
            url = url_info.get("url", "") if isinstance(url_info, dict) else url_info.url
            url_type = classify_url(url, product_url_pattern=product_url_pattern)
            if url_type == URLType.KIT:
                report.kits_total += 1
                hair_urls.append(url)  # Extract kits too
            elif url_type == URLType.NON_HAIR:
                report.non_hair_total += 1
            elif url_type in (URLType.PRODUCT, URLType.CATEGORY):
                report.hair_total += 1
                hair_urls.append(url)  # Extract both products and categories
            else:
                report.non_hair_total += 1

        # Extract each product URL
        for url in hair_urls:
            try:
                product_data = self._extract_product(url, brand_slug, inci_selectors, name_selectors, image_selectors=image_selectors, blueprint_config=blueprint, section_label_map=section_label_map, price_selectors=price_selectors, description_selectors=description_selectors)
                if not product_data:
                    continue

                qa_result = run_product_qa(
                    product_data, allowed_domains,
                    has_section_context=getattr(product_data, "has_section_context", False),
                )
                product_id = self._repo.upsert_product(product_data, qa_result)
                report.extracted_total += 1

                # Dual-write to normalized tables
                from src.storage.normalized_writer import NormalizedWriter
                if not hasattr(self, '_normalized_writer'):
                    self._normalized_writer = NormalizedWriter(self._session)

                saved_product = self._repo.get_product_by_id(product_id)
                if saved_product:
                    try:
                        self._normalized_writer.write_all(saved_product)
                    except Exception as e:
                        logger.warning(f"Normalized write failed for {url}: {e}")
                    # Compute the AI-facing Gold tier on every scrape (never
                    # overwrite a human gold_rejected verdict).
                    try:
                        ev = evaluate_gold(saved_product, session=self._session)
                        if saved_product.gold_status != "gold_rejected":
                            saved_product.gold_status = ev.gold_status.value
                            saved_product.gold_blockers = ev.blockers_as_dicts()
                            saved_product.gold_evaluated_at = datetime.now(timezone.utc)
                    except Exception as e:
                        logger.warning(f"Gold eval failed for {url}: {e}")

                if qa_result.status == QAStatus.VERIFIED_INCI:
                    report.verified_inci_total += 1
                elif qa_result.status == QAStatus.CATALOG_ONLY:
                    report.catalog_only_total += 1
                elif qa_result.status == QAStatus.QUARANTINED:
                    report.quarantined_total += 1

                # Stop-the-line check
                if report.extracted_total >= 5 and report.failure_rate > STOP_THE_LINE_THRESHOLD:
                    logger.warning(
                        f"Stop-the-line triggered for {brand_slug}: "
                        f"failure_rate={report.failure_rate:.2%}"
                    )
                    report.errors.append(
                        f"stop_the_line: failure_rate={report.failure_rate:.2%} "
                        f"after {report.extracted_total} products"
                    )
                    break

            except Exception as e:
                logger.error(f"Error extracting {url}: {e}")
                report.errors.append(f"extraction_error: {url}: {str(e)}")

        report.complete()

        # Save coverage stats
        stats = generate_coverage_stats(report)
        self._repo.upsert_brand_coverage(stats)
        self._session.commit()

        logger.info(
            f"Brand {brand_slug} complete: "
            f"{report.extracted_total} extracted, "
            f"{report.verified_inci_total} verified ({report.verified_inci_rate:.1%}), "
            f"{report.quarantined_total} quarantined"
        )

        return report

    def _try_llm_extraction(self, url: str, html: str, product_name: str) -> dict | None:
        """Use LLM to extract INCI and description from page text."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        page_text = soup.get_text(separator="\n", strip=True)

        prompt = f"""Extract product data from this page text.

Return JSON with:
- "inci_ingredients": list of ingredients (ONLY if you find a complete ingredient list)
- "description": product description string
- "separator": the separator character used between ingredients (e.g. ",", ";", "/")

Rules:
- Accept ingredient names in Portuguese (e.g. "sulfato de sodio laurete") as well as standard INCI names
- Ignore marketing text, usage instructions, and benefits — only extract the actual ingredient list
- Do NOT guess or infer ingredients. Only extract what is explicitly listed.
- A complete list typically starts with "Aqua" or "Water" and contains 5+ ingredients

Product: {product_name}
"""
        result = self._llm_client.extract_structured(page_text=page_text, prompt=prompt, max_tokens=2048)
        if result and (result.get("inci_ingredients") or result.get("description")):
            return result
        return None

    def _extract_product(
        self,
        url: str,
        brand_slug: str,
        inci_selectors: list[str],
        name_selectors: list[str],
        image_selectors: list[str] | None = None,
        blueprint_config: dict | None = None,
        section_label_map: dict | None = None,
        price_selectors: list[str] | None = None,
        description_selectors: list[str] | None = None,
    ) -> ProductExtraction | None:
        # Fetch page HTML
        if not self._browser:
            logger.debug(f"No browser, skipping {url}")
            return None

        extraction_cfg = (blueprint_config or {}).get("extraction", {})
        wait_for = extraction_cfg.get("wait_for_selector")
        requires_js = extraction_cfg.get("requires_js", False)
        expand = bool(wait_for) or requires_js  # Expand accordions for JS-rendered pages
        try:
            html = self._browser.fetch_page(url, wait_for=wait_for, expand_accordions=expand)
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

        # Deterministic extraction
        det_result = extract_product_deterministic(
            html=html,
            url=url,
            inci_selectors=inci_selectors,
            name_selectors=name_selectors,
            image_selectors=image_selectors or None,
            section_label_map=section_label_map,
            price_selectors=price_selectors or None,
            description_selectors=description_selectors or None,
        )

        # Blocked page (WAF/Cloudflare challenge): don't drop it silently — route
        # to an explicit quarantine so it surfaces in Ops for a re-scrape via a
        # different fetch path (client feedback: brands that "extraíram nada").
        if det_result.get("blocked_reason"):
            slug = url.rstrip("/").rsplit("/", 1)[-1] or url
            return ProductExtraction(
                brand_slug=brand_slug,
                product_name=f"[bloqueado] {slug}"[:200],
                product_url=url,
                hair_relevance_reason=f"blocked:{det_result['blocked_reason']}",
                confidence=0.0,
            )

        # Fallback for pages that dump all copy into one description blob with
        # inline "Modo de uso:" / "Composição:" markers and no separate DOM
        # sections (client feedback 2026-06: Bio-instinto, Avatim, alphahall...).
        # Split those out so usage/composition stop landing in description.
        # Only acts when care_usage is empty AND a real "como usar" marker exists.
        if det_result.get("description") and not det_result.get("care_usage"):
            from src.extraction.description_splitter import split_description_blob

            _split = split_description_blob(det_result["description"])
            if _split.get("care_usage"):
                det_result["care_usage"] = _split["care_usage"]
                if _split.get("description"):
                    det_result["description"] = _split["description"]
                if not det_result.get("composition") and _split.get("composition"):
                    det_result["composition"] = _split["composition"]

        product_name = det_result.get("product_name") or ""
        if not product_name:
            return None

        # Gender and type detection
        gender = detect_gender_target(product_name, url)
        product_type = normalize_product_type(product_name)

        # Hair relevance — preserva o motivo real, mesmo quando NÃO é cabelo.
        # qa_gate detecta o prefixo "non_hair:" e seta verification_status='quarantined'
        # com quarantine_reason apropriado. Não-cabelo entra como quarentena, não como
        # ativo, pra reviewer poder auditar na aba Quarentena.
        relevant, reason = is_hair_relevant_by_keywords(product_name, url, description=det_result.get("description") or "")

        # INCI processing
        inci_raw = det_result.get("inci_raw")
        inci_list = None
        confidence = 0.0
        extraction_method = det_result.get("extraction_method")
        description = det_result.get("description")

        inci_source = det_result.get("inci_source")
        has_section_context = inci_source in ("section_classifier", "tab_label_heuristic")

        if inci_raw:
            inci_result = extract_and_validate_inci(inci_raw, has_section_context=has_section_context)
            if inci_result.valid:
                inci_list = inci_result.cleaned
                confidence = 0.90
            else:
                confidence = 0.30

        # LLM fallback: if no INCI found and LLM is available + blueprint enables it
        if inci_list is None and self._llm_client and self._llm_client.can_call:
            if (blueprint_config or {}).get("use_llm_fallback", False):
                try:
                    llm_result = self._try_llm_extraction(url, html, product_name)
                    if llm_result:
                        if llm_result.get("inci_ingredients"):
                            inci_raw_llm = ", ".join(llm_result["inci_ingredients"])
                            inci_val = extract_and_validate_inci(inci_raw_llm)
                            if inci_val.valid:
                                inci_list = inci_val.cleaned
                                confidence = 0.85
                                extraction_method = ExtractionMethod.LLM_GROUNDED.value
                                logger.info(f"LLM fallback found INCI for {url}")
                        if not description and llm_result.get("description"):
                            description = llm_result["description"]
                except Exception as e:
                    logger.warning(f"LLM fallback failed for {url}: {e}")

        # Category
        product_category = normalize_category(product_type, product_name)

        # How-to-use: the deterministic extractor lands "modo de uso / como usar"
        # in care_usage. Promote it to the canonical usage_instructions field
        # (read by Ops UI, label engine and the Gold gate) only when it reads
        # like real instructions — not a leaked tab label or a description.
        care_usage_val = det_result.get("care_usage")
        usage_instructions = care_usage_val if is_real_usage_instructions(care_usage_val) else None

        return ProductExtraction(
            brand_slug=brand_slug,
            product_name=product_name,
            product_url=url,
            image_url_main=det_result.get("image_url_main"),
            gender_target=GenderTarget(gender) if gender in [e.value for e in GenderTarget] else GenderTarget.UNKNOWN,
            hair_relevance_reason=reason or "product_url",
            product_type_raw=product_name,
            product_type_normalized=product_type,
            product_category=product_category,
            inci_ingredients=inci_list,
            description=description,
            usage_instructions=usage_instructions,
            composition=det_result.get("composition"),
            care_usage=care_usage_val,
            benefits_claims=_benefits_to_list(det_result.get("benefits")),
            price=det_result.get("price"),
            currency=det_result.get("currency"),
            confidence=confidence,
            extraction_method=extraction_method,
            has_section_context=has_section_context,
            evidence=det_result.get("evidence", []),
        )
