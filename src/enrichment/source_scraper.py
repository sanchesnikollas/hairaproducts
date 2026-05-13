from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

import re

from src.core.browser import BrowserClient
from src.discovery.product_discoverer import ProductDiscoverer
from src.enrichment.vtex_catalog import _extract_inci_from_description, fetch_vtex_specs
from src.extraction.deterministic import extract_product_deterministic
from src.extraction.inci_extractor import extract_and_validate_inci
from src.storage.orm_models import ExternalInciORM

# Lightweight cosmetic-ingredient sniff. Used to gate raw HTML chunks that the
# blueprint CSS selectors capture from a marketing description: only treat the
# chunk as an INCI candidate if it contains at least one of these known tokens.
# Avoids storing pages of marketing prose that happen to have commas as
# "ingredients" (the original 32/1111 false-positive class on Beleza na Web).
_INCI_MARKER_TOKENS = re.compile(
    r"\b("
    r"aqua|water|glycerin|cetearyl\s+alcohol|cetyl\s+alcohol|sodium\s+laureth"
    r"|sodium\s+lauryl|cocamidopropyl|dimethicone|fragrance|parfum|propylene"
    r"|cocoamidopropil|cocamide|panthenol|pantenol|edta|phenoxyethanol"
    r"|tocopherol|polyquaternium|cocos\s+nucifera|argan|olea\s+europaea"
    r"|ricinus\s+communis|amodimeticona|metossulfato|laureth|cloreto\s+de"
    r"|álcool\s+cet|alcool\s+cet|fragr[âa]ncia|extrato\s+de"
    r"|isopropyl|trimethicone|behentrimonium|stearamidopropyl"
    r")\b",
    re.IGNORECASE,
)


def _looks_like_real_inci(text: str) -> bool:
    """Return True if `text` contains at least one common cosmetic-ingredient
    token. Used as a cheap gate before treating a CSS-selector capture as INCI.

    This complements `validate_inci_list` (which only checks structure: 3+ comma
    separated phrases) by requiring a domain marker. Without this, generic
    marketing prose with commas passes structural checks but produces nonsense
    "ingredient" lists.
    """
    if not text:
        return False
    return bool(_INCI_MARKER_TOKENS.search(text))


# An INCI list always opens with a primary cosmetic ingredient (typically water).
# A real INCI is hundreds of characters of comma-separated chemical names; a
# marketing paragraph that happens to mention "fragrância" once will not have
# Aqua/Água/Water near the start.
_INCI_ANCHOR_PATTERN = re.compile(
    r"\b(aqua|water|[áa]gua)\b[^\.\n]{0,400}[,;|/]",
    re.IGNORECASE,
)


def _has_inci_anchor(text: str) -> bool:
    """Return True if `text` looks like the start of an INCI list (Aqua/Água as
    one of the first comma-delimited tokens).
    """
    if not text:
        return False
    # Only look at the leading section of the captured text.
    head = text[:600]
    return bool(_INCI_ANCHOR_PATTERN.search(head))

logger = logging.getLogger("haira.enrichment.source_scraper")

SOURCES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "blueprints" / "sources"


def load_source_blueprint(source_slug: str) -> dict | None:
    filepath = SOURCES_DIR / f"{source_slug}.yaml"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_brand_from_url(url: str, brand_slug_map: dict) -> str | None:
    url_lower = url.lower()
    for url_segment, haira_slug in brand_slug_map.items():
        if url_segment.lower() in url_lower:
            return haira_slug
    return None


def scrape_source(
    session: Session,
    source_slug: str,
    brand_filter: str | None = None,
) -> dict:
    bp = load_source_blueprint(source_slug)
    if not bp:
        raise ValueError(f"No source blueprint found for {source_slug}")

    brand_slug_map = bp.get("brand_slug_map", {})
    extraction_config = bp.get("extraction", {})

    # Setup browser — use curl_cffi for discovery (fast), Playwright for JS extraction
    http_client = extraction_config.get("http_client", "")
    ssl_verify = extraction_config.get("ssl_verify", True)
    requires_js = extraction_config.get("requires_js", False)
    use_vtex_api = extraction_config.get("use_vtex_catalog_api", False)

    # Discovery always uses curl_cffi (sitemaps are XML, no JS needed)
    discovery_browser = BrowserClient(use_curl_cffi=True, ssl_verify=ssl_verify)

    # Extraction browser: Playwright if requires_js, else curl_cffi
    if requires_js:
        extraction_browser = BrowserClient(use_httpx=False, ssl_verify=ssl_verify)
    elif http_client == "curl_cffi":
        extraction_browser = BrowserClient(use_curl_cffi=True, ssl_verify=ssl_verify)
    else:
        extraction_browser = BrowserClient(use_httpx=True, ssl_verify=ssl_verify)

    # Companion curl_cffi session used by the VTEX catalog API helper.
    # We always create one when use_vtex_api is on, regardless of the main
    # browser flavor (e.g., Playwright pages still expose the public catalog API).
    vtex_session = None
    if use_vtex_api:
        api_browser = BrowserClient(use_curl_cffi=True, ssl_verify=ssl_verify)
        api_browser._ensure_curl_cffi()
        vtex_session = api_browser._curl_session

    # Discover URLs (fast, curl_cffi)
    discoverer = ProductDiscoverer(browser=discovery_browser)
    discovered = discoverer.discover(bp)

    # Filter by brand if requested
    if brand_filter:
        discovered = [
            d for d in discovered
            if detect_brand_from_url(d.url, {brand_filter: brand_filter})
            or brand_filter in d.url.lower()
        ]

    stats = {"discovered": len(discovered), "scraped": 0, "with_inci": 0, "skipped": 0}

    for disc_url in discovered:
        url = disc_url.url
        brand = detect_brand_from_url(url, brand_slug_map)
        if not brand:
            stats["skipped"] += 1
            continue
        if brand_filter and brand != brand_filter:
            stats["skipped"] += 1
            continue

        try:
            html = extraction_browser.fetch_page(url)
            if not html or len(html) < 500:
                continue

            det_result = extract_product_deterministic(
                html, url,
                inci_selectors=extraction_config.get("inci_selectors"),
                name_selectors=extraction_config.get("name_selectors"),
                image_selectors=extraction_config.get("image_selectors"),
                section_label_map=extraction_config.get("section_label_map"),
            )

            product_name = det_result.get("product_name")
            inci_raw = det_result.get("inci_raw")

            # If the deterministic extractor picked up text from a marketing
            # description container (e.g., `.product-description-content` on
            # Beleza na Web), narrow it down to the inline "Composição: …" /
            # "Ingredientes: …" block when one is present. This avoids
            # persisting paragraphs of prose that happen to contain commas.
            #
            # Two-step gate:
            #   1. Try to extract the inline INCI block (requires a header
            #      like "Composição:" inside the captured text).
            #   2. If no header, require BOTH structural cosmetic-ingredient
            #      markers AND a clear "anchor" — at least an INCI primary
            #      ingredient at the front of the list (Aqua/Água/Water).
            #      Without that anchor, marketing prose that incidentally
            #      mentions one cosmetic term (fragrância, etc.) still
            #      passes; the anchor check kills that class of false
            #      positives.
            if inci_raw:
                narrowed = _extract_inci_from_description(inci_raw)
                if narrowed:
                    inci_raw = narrowed
                elif not (_looks_like_real_inci(inci_raw) and _has_inci_anchor(inci_raw)):
                    inci_raw = None

            # VTEX catalog API path: if blueprint opts in, query the public
            # catalog endpoint to read Composição/Ingredientes from
            # `allSpecifications`. This is the single fix that unlocks INCI on
            # storefronts where specifications render client-side and the
            # SSR HTML contains only nav/marketing copy (Época Cosméticos).
            if use_vtex_api and vtex_session is not None and not inci_raw:
                api_data = fetch_vtex_specs(vtex_session, url, ssr_html=html)
                if api_data:
                    if not product_name and api_data.get("product_name"):
                        product_name = api_data["product_name"]
                    if api_data.get("inci_raw"):
                        inci_raw = api_data["inci_raw"]
                        logger.debug(
                            "vtex_catalog hit: %s key=%s",
                            url, api_data.get("inci_source_key"),
                        )

            # Parse INCI. We accept the parsed list only when both structural
            # validation (`extract_and_validate_inci`) AND content fingerprints
            # agree: the raw text contains a cosmetic-ingredient marker and
            # opens with an INCI primary ingredient. The double check rejects
            # marketing prose that happens to be punctuated like an ingredient
            # list — the failure class behind the original 32/1111 false
            # positives on Beleza na Web.
            inci_list = None
            if inci_raw:
                inci_result = extract_and_validate_inci(inci_raw, has_section_context=True)
                if (
                    inci_result.valid
                    and _looks_like_real_inci(inci_raw)
                    and _has_inci_anchor(inci_raw)
                ):
                    inci_list = inci_result.cleaned

            # Detect product type
            from src.enrichment.matcher import detect_product_type
            product_type = detect_product_type(product_name or "")

            # Upsert to external_inci
            existing = (
                session.query(ExternalInciORM)
                .filter(
                    ExternalInciORM.source == source_slug,
                    ExternalInciORM.source_url == url,
                )
                .first()
            )
            if existing:
                existing.product_name = product_name
                existing.product_type = product_type
                existing.inci_raw = inci_raw
                existing.inci_ingredients = inci_list
                existing.brand_slug = brand
                existing.updated_at = datetime.now(timezone.utc)
            else:
                record = ExternalInciORM(
                    source=source_slug,
                    source_url=url,
                    brand_slug=brand,
                    product_name=product_name,
                    product_type=product_type,
                    inci_raw=inci_raw,
                    inci_ingredients=inci_list,
                )
                session.add(record)

            stats["scraped"] += 1
            if inci_list:
                stats["with_inci"] += 1

            if stats["scraped"] % 50 == 0:
                session.commit()
                logger.info("Progress: %d scraped, %d with INCI", stats["scraped"], stats["with_inci"])

        except Exception as e:
            logger.warning("Error scraping %s: %s", url, e)
            continue

    session.commit()
    return stats
