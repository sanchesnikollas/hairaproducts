# src/pipeline/coverage_engine.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.models import ProductExtraction, GenderTarget, ExtractionMethod, QAResult, QAStatus
from src.core.qa_gate import run_product_qa
from src.core.taxonomy import normalize_product_type, normalize_category, detect_gender_target, is_hair_relevant_by_keywords
from src.discovery.url_classifier import classify_url, URLType
from src.extraction.deterministic import extract_product_deterministic
from src.extraction.inci_extractor import extract_and_validate_inci
from src.pipeline.report_generator import BrandReport, generate_coverage_stats
from src.storage.repository import ProductRepository

logger = logging.getLogger(__name__)

STOP_THE_LINE_THRESHOLD = 0.50


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

        report.discovered_total = len(discovered_urls)

        # Classify URLs
        hair_urls = []
        for url_info in discovered_urls:
            url = url_info.get("url", "") if isinstance(url_info, dict) else url_info.url
            url_type = classify_url(url)
            if url_type == URLType.KIT:
                report.kits_total += 1
            elif url_type == URLType.NON_HAIR:
                report.non_hair_total += 1
            elif url_type in (URLType.PRODUCT, URLType.CATEGORY):
                report.hair_total += 1
                if url_type == URLType.PRODUCT:
                    hair_urls.append(url)
            else:
                report.non_hair_total += 1

        # Extract each product URL
        for url in hair_urls:
            try:
                product_data = self._extract_product(url, brand_slug, inci_selectors, name_selectors, image_selectors=image_selectors, blueprint_config=blueprint)
                if not product_data:
                    continue

                qa_result = run_product_qa(product_data, allowed_domains)
                self._repo.upsert_product(product_data, qa_result)
                report.extracted_total += 1

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

        prompt = (
            "Extract the following fields from this hair product page.\n"
            f"Product: {product_name}\n\n"
            "Return JSON with these fields:\n"
            "- inci_ingredients: list of individual INCI ingredient names (strings), or null if not found\n"
            "- description: product description text, or null if not found\n\n"
            "IMPORTANT: Only extract INCI ingredients if you find a complete ingredient list "
            "(typically starting with 'Aqua' or 'Water'). Do NOT guess or infer ingredients."
        )
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
    ) -> ProductExtraction | None:
        # Fetch page HTML
        if not self._browser:
            logger.debug(f"No browser, skipping {url}")
            return None

        try:
            html = self._browser.fetch_page(url)
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
        )

        product_name = det_result.get("product_name") or ""
        if not product_name:
            return None

        # Gender and type detection
        gender = detect_gender_target(product_name, url)
        product_type = normalize_product_type(product_name)

        # Hair relevance
        relevant, reason = is_hair_relevant_by_keywords(product_name, url)
        if not relevant:
            reason = f"url_classified_as_product"

        # INCI processing
        inci_raw = det_result.get("inci_raw")
        inci_list = None
        confidence = 0.0
        extraction_method = det_result.get("extraction_method")
        description = det_result.get("description")

        if inci_raw:
            inci_result = extract_and_validate_inci(inci_raw)
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
            price=det_result.get("price"),
            currency=det_result.get("currency"),
            confidence=confidence,
            extraction_method=extraction_method,
            evidence=det_result.get("evidence", []),
        )
