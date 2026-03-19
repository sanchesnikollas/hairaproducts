#!/usr/bin/env python3
"""Extract L'Occitane US hair products using curl_cffi to bypass DataDome WAF.

DataDome WAF blocks httpx and Playwright. curl_cffi with Chrome impersonation
works but requires a fresh session per request (DataDome fingerprints sessions).
"""
from __future__ import annotations

import logging
import re
import sys
import time
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from sqlalchemy.orm import Session as SASession

from src.core.models import ProductExtraction, GenderTarget, ExtractionMethod, QAStatus
from src.core.qa_gate import run_product_qa
from src.core.taxonomy import normalize_product_type, normalize_category, detect_gender_target
from src.extraction.inci_extractor import extract_and_validate_inci
from src.storage.database import get_engine
from src.storage.orm_models import Base
from src.storage.repository import ProductRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

BRAND_SLUG = "loccitane-us"
SITEMAP_URL = "https://www.loccitane.com/en-us/sitemap_1.xml"
HAIR_KEYWORDS = ["shampoo", "conditioner", "hair", "scalp", "masque", "repair", "volume", "aromachologie"]
DELAY = 5  # seconds between requests
INCI_SEPARATOR = " - "


def discover_hair_urls() -> list[str]:
    """Get hair product URLs from sitemap."""
    log.info("Fetching sitemap...")
    client = httpx.Client(follow_redirects=True, timeout=30)
    resp = client.get(SITEMAP_URL)
    resp.raise_for_status()

    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(resp.text)
    all_urls = [loc.text for loc in root.findall(".//ns:loc", ns)]
    log.info(f"Sitemap has {len(all_urls)} URLs")

    product_pattern = re.compile(r"^https://www\.loccitane\.com/en-us/[\w%-]+-[\w]+\.html$")
    hair_urls = []
    for url in all_urls:
        if not product_pattern.match(url):
            continue
        lower = url.lower()
        if any(kw in lower for kw in HAIR_KEYWORDS):
            hair_urls.append(url)

    log.info(f"Found {len(hair_urls)} hair product URLs")
    client.close()
    return hair_urls


def fetch_page(url: str) -> str | None:
    """Fetch a page using curl_cffi with fresh session (bypasses DataDome)."""
    try:
        session = cffi_requests.Session(impersonate="chrome")
        resp = session.get(url, timeout=30)
        session.close()
        if resp.status_code != 200:
            log.warning(f"HTTP {resp.status_code} for {url}")
            return None
        html = resp.text
        if len(html) < 5000:
            log.warning(f"Suspiciously short page for {url} (len={len(html)})")
            return None
        return html
    except Exception as e:
        log.error(f"Fetch error for {url}: {e}")
        return None


def extract_product(html: str, url: str) -> ProductExtraction | None:
    """Extract product data from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Product name from h1
    h1 = soup.find("h1")
    if not h1:
        return None
    name = h1.get_text(strip=True)
    # Remove appended size (e.g., "Intensive Repair Shampoo75 ml")
    name = re.sub(r"\d+\s*(?:ml|g|oz|fl\.?\s*oz)\.?$", "", name, flags=re.IGNORECASE).strip()
    if not name or name.lower().startswith("this page"):
        return None

    # INCI from .ingredients-list p
    inci_list = None
    confidence = 0.0
    inci_el = soup.select_one(".ingredients-list p") or soup.select_one(".ingredients-list")
    if inci_el:
        raw = inci_el.get_text(strip=True)
        if len(raw) > 30:
            parts = [p.strip() for p in raw.split(INCI_SEPARATOR) if p.strip()]
            if len(parts) >= 5:
                result = extract_and_validate_inci(", ".join(parts))
                if result.valid:
                    inci_list = result.cleaned
                    confidence = 0.90

    # Description
    desc = None
    desc_el = soup.select_one(".pdp-product-description") or soup.select_one(".product-description")
    if desc_el:
        desc = desc_el.get_text(strip=True)[:2000]

    # Image
    image = None
    img_el = soup.select_one('img[src*="demandware.static"]') or soup.select_one(".product-image img")
    if img_el and img_el.get("src"):
        image = img_el["src"]
        if image.startswith("//"):
            image = "https:" + image

    # Gender and type
    gender = detect_gender_target(name, url)
    product_type = normalize_product_type(name)
    category = normalize_category(product_type, name)

    return ProductExtraction(
        brand_slug=BRAND_SLUG,
        product_name=name,
        product_url=url,
        image_url_main=image,
        gender_target=GenderTarget(gender) if gender in [e.value for e in GenderTarget] else GenderTarget.UNKNOWN,
        product_type_raw=product_type,
        product_type_normalized=product_type,
        product_category=category,
        is_kit=False,
        hair_relevance_reason="url_hair_keyword",
        inci_ingredients=inci_list,
        description=desc,
        confidence=confidence,
        extraction_method=ExtractionMethod.HTML_SELECTOR.value,
    )


def main():
    hair_urls = discover_hair_urls()
    if not hair_urls:
        log.error("No hair URLs found")
        sys.exit(1)

    engine = get_engine()
    Base.metadata.create_all(engine)

    stats = {"extracted": 0, "verified": 0, "catalog_only": 0, "failed": 0, "blocked": 0}

    with SASession(engine) as session:
        repo = ProductRepository(session)

        for i, url in enumerate(hair_urls):
            log.info(f"[{i+1}/{len(hair_urls)}] {url}")
            time.sleep(DELAY)

            html = fetch_page(url)
            if not html:
                stats["blocked"] += 1
                continue

            product = extract_product(html, url)
            if not product:
                stats["failed"] += 1
                continue

            qa = run_product_qa(product, ["www.loccitane.com"])
            repo.upsert_product(product, qa)
            stats["extracted"] += 1

            if qa.status == QAStatus.VERIFIED_INCI:
                stats["verified"] += 1
            else:
                stats["catalog_only"] += 1

            if stats["extracted"] % 5 == 0:
                session.commit()
                log.info(f"Progress: {stats}")

        session.commit()

        # Update coverage
        from src.pipeline.report_generator import BrandReport, generate_coverage_stats
        report = BrandReport(brand_slug=BRAND_SLUG)
        report.discovered_total = len(hair_urls)
        report.hair_total = len(hair_urls)
        report.extracted_total = stats["extracted"]
        report.verified_inci_total = stats["verified"]
        report.catalog_only_total = stats["catalog_only"]
        report.complete()
        coverage_stats = generate_coverage_stats(report)
        repo.upsert_brand_coverage(coverage_stats)
        session.commit()

    log.info(f"\nDone! Final stats: {stats}")


if __name__ == "__main__":
    main()
