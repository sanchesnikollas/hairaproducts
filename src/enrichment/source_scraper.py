from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from src.core.browser import BrowserClient
from src.discovery.product_discoverer import ProductDiscoverer
from src.extraction.deterministic import extract_product_deterministic
from src.extraction.inci_extractor import extract_and_validate_inci
from src.storage.orm_models import ExternalInciORM

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

    # Discovery always uses curl_cffi (sitemaps are XML, no JS needed)
    discovery_browser = BrowserClient(use_curl_cffi=True, ssl_verify=ssl_verify)

    # Extraction browser: Playwright if requires_js, else curl_cffi
    if requires_js:
        extraction_browser = BrowserClient(use_httpx=False, ssl_verify=ssl_verify)
    elif http_client == "curl_cffi":
        extraction_browser = BrowserClient(use_curl_cffi=True, ssl_verify=ssl_verify)
    else:
        extraction_browser = BrowserClient(use_httpx=True, ssl_verify=ssl_verify)

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

            # Parse INCI
            inci_list = None
            if inci_raw:
                inci_result = extract_and_validate_inci(inci_raw, has_section_context=True)
                if inci_result.valid:
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
