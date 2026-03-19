#!/usr/bin/env python3
"""
Comprehensive Amend product extraction — ALL categories, ALL products (including kits & coloração).

Phase 1: Discover all product URLs by paginating AJAX category endpoints
Phase 2: Extract product data via BrowserClient + deterministic pipeline
Phase 3: Update coverage stats

Usage:
    PYTHONPATH=. python3 scripts/amend_full_extraction.py
    PYTHONPATH=. python3 scripts/amend_full_extraction.py --discover-only
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from src.core.browser import BrowserClient
from src.core.models import ProductExtraction, GenderTarget
from src.core.qa_gate import run_product_qa
from src.core.taxonomy import normalize_product_type, detect_gender_target, is_hair_relevant_by_keywords
from src.extraction.deterministic import extract_product_deterministic
from src.extraction.inci_extractor import extract_and_validate_inci
from src.storage.database import get_engine
from src.storage.orm_models import ProductORM, BrandCoverageORM
from src.storage.repository import ProductRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BRAND = "amend"
ALLOWED_DOMAINS = ["www.amend.com.br"]
BASE = "https://www.amend.com.br"

# All productive categories on the Amend SFCC site
CATEGORIES = [
    "shampoo",
    "condicionador",
    "mascara",
    "finalizacao",
    "coloracao",
    "transformacao",
    "tratamento-tipo-produto",
    "kits",
    "lancamentos",
    "tratamento",
    "tratamento-kits-de-tratamento",
]

# Blueprint selectors for extraction
INCI_SELECTORS = [
    ".product-ingredients p",
    ".product-ingredients",
    "p.description-product-page",
    ".greyBackground p.description-product-page",
    "#ingredientes p",
    "#composicao p",
    '[data-tab="ingredientes"] p',
    ".product-description p",
]
NAME_SELECTORS = ["h1.product-name", "h1", ".product-title", ".product-name"]

BATCH_COMMIT_SIZE = 20

# Demandware/SFCC uses sz param for page size — sz=500 returns all in one request
SFCC_PAGE_SIZE = 500

# Exclusion patterns for non-product links
_NON_PRODUCT = ("/on/demandware", "/busca/", "/carrinho", "/login", "/wishlist")


def discover_all_urls() -> set[str]:
    """Phase 1: Fetch AJAX category pages with sz=500 to get all product tiles at once.

    Extracts the first product link from each .grid-tile element. This handles
    all Amend URL formats:
      - /product-name/p/ID.html   (old format)
      - /product-name/ID.html     (new format, no /p/)
      - /p/ID.html                (short format)
    """
    all_urls: set[str] = set()
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        timeout=30.0,
        follow_redirects=True,
    )

    try:
        for cat in CATEGORIES:
            url = f"{BASE}/busca/?cgid={cat}&format=ajax&start=0&sz={SFCC_PAGE_SIZE}"
            try:
                resp = client.get(url)
                soup = BeautifulSoup(resp.text, "html.parser")

                tiles = soup.select(".grid-tile, .product-tile")
                cat_urls: set[str] = set()

                for tile in tiles:
                    for a in tile.find_all("a", href=True):
                        href = a["href"]
                        if ".html" not in href:
                            continue
                        if any(ex in href for ex in _NON_PRODUCT):
                            continue
                        full = urljoin(BASE + "/", href.split("?")[0])
                        if "amend.com.br" in full:
                            cat_urls.add(full)
                            break  # first product link per tile

                all_urls.update(cat_urls)
                logger.info(
                    f"  Category '{cat}': {len(tiles)} tiles → {len(cat_urls)} URLs "
                    f"(running total: {len(all_urls)})"
                )
            except Exception as e:
                logger.warning(f"  Failed category '{cat}': {e}")

            time.sleep(0.3)
    finally:
        client.close()

    return all_urls


def classify_urls(urls: set[str]) -> tuple[list[str], list[str]]:
    """Separate individual products from kits."""
    individual = []
    kits = []
    for url in sorted(urls):
        lower = url.lower()
        if "kit-" in lower or "/kit " in lower:
            kits.append(url)
        else:
            individual.append(url)
    return individual, kits


def extract_single_product(
    url: str, browser: BrowserClient, repo: ProductRepository, session: Session
) -> str:
    """Extract one product and return its status ('verified'|'catalog'|'quarantined'|'failed')."""
    html = browser.fetch_page(url)

    det_result = extract_product_deterministic(
        html=html,
        url=url,
        inci_selectors=INCI_SELECTORS,
        name_selectors=NAME_SELECTORS,
    )

    product_name = det_result.get("product_name") or ""
    if not product_name:
        return "failed"

    gender = detect_gender_target(product_name, url)
    product_type = normalize_product_type(product_name)
    relevant, reason = is_hair_relevant_by_keywords(product_name, url)
    if not relevant:
        reason = "url_classified_as_product"

    inci_raw = det_result.get("inci_raw")
    inci_list = None
    confidence = 0.0
    if inci_raw:
        inci_result = extract_and_validate_inci(inci_raw)
        if inci_result.valid:
            inci_list = inci_result.cleaned
            confidence = 0.90
        else:
            confidence = 0.30

    extraction = ProductExtraction(
        brand_slug=BRAND,
        product_name=product_name,
        product_url=url,
        image_url_main=det_result.get("image_url_main"),
        gender_target=(
            GenderTarget(gender)
            if gender in [e.value for e in GenderTarget]
            else GenderTarget.UNKNOWN
        ),
        hair_relevance_reason=reason or "product_url",
        product_type_raw=product_name,
        product_type_normalized=product_type,
        inci_ingredients=inci_list,
        description=det_result.get("description"),
        price=det_result.get("price"),
        currency=det_result.get("currency"),
        confidence=confidence,
        extraction_method=det_result.get("extraction_method"),
        evidence=det_result.get("evidence", []),
    )

    qa_result = run_product_qa(extraction, ALLOWED_DOMAINS)
    repo.upsert_product(extraction, qa_result)

    return qa_result.status.value


def extract_products(urls: list[str], session: Session, browser: BrowserClient) -> dict:
    """Phase 2: Extract all products from URL list."""
    repo = ProductRepository(session)
    stats = {"extracted": 0, "verified_inci": 0, "catalog_only": 0, "quarantined": 0, "failed": 0}

    for i, url in enumerate(urls, 1):
        logger.info(f"[{i}/{len(urls)}] {url}")
        try:
            status = extract_single_product(url, browser, repo, session)
            if status == "failed":
                stats["failed"] += 1
                logger.warning(f"  SKIP: No product name found")
            else:
                stats["extracted"] += 1
                stats[status] = stats.get(status, 0) + 1
                logger.info(f"  → {status.upper()}")
        except Exception as e:
            stats["failed"] += 1
            logger.error(f"  FAILED: {e}")

        # Commit in batches
        if i % BATCH_COMMIT_SIZE == 0:
            session.commit()
            logger.info(f"  --- Committed batch ({i}/{len(urls)}) ---")

    session.commit()
    return stats


def update_coverage(session: Session):
    """Phase 3: Update brand coverage stats."""
    products = session.query(ProductORM).filter(ProductORM.brand_slug == BRAND).all()
    total = len(products)
    verified = sum(1 for p in products if p.verification_status == "verified_inci")
    catalog = sum(1 for p in products if p.verification_status == "catalog_only")
    quarantined = sum(1 for p in products if p.verification_status == "quarantined")
    rate = verified / total if total > 0 else 0.0

    coverage = (
        session.query(BrandCoverageORM).filter(BrandCoverageORM.brand_slug == BRAND).first()
    )
    if coverage:
        coverage.extracted_total = total
        coverage.verified_inci_total = verified
        coverage.verified_inci_rate = rate
        coverage.catalog_only_total = catalog
        coverage.quarantined_total = quarantined
        coverage.updated_at = datetime.now(timezone.utc)
    else:
        coverage = BrandCoverageORM(
            brand_slug=BRAND,
            extracted_total=total,
            verified_inci_total=verified,
            verified_inci_rate=rate,
            catalog_only_total=catalog,
            quarantined_total=quarantined,
            status="completed",
        )
        session.add(coverage)

    session.commit()
    logger.info(
        f"Coverage updated: {total} total, {verified} verified ({rate:.1%}), "
        f"{catalog} catalog, {quarantined} quarantined"
    )


def main():
    parser = argparse.ArgumentParser(description="Amend full product extraction")
    parser.add_argument("--discover-only", action="store_true", help="Only discover URLs, don't extract")
    args = parser.parse_args()

    # ── Phase 1: Discover ──
    logger.info("=" * 60)
    logger.info("PHASE 1: Discovering ALL product URLs from amend.com.br...")
    logger.info("=" * 60)

    all_urls = discover_all_urls()
    individual, kits = classify_urls(all_urls)
    logger.info(f"\nDiscovered {len(all_urls)} total URLs:")
    logger.info(f"  Individual products: {len(individual)}")
    logger.info(f"  Kits:                {len(kits)}")

    # Save URL list for reference
    os.makedirs("data", exist_ok=True)
    url_file = "data/amend_all_urls.txt"
    with open(url_file, "w") as f:
        f.write(f"# Amend product URLs discovered at {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"# Total: {len(all_urls)} ({len(individual)} individual + {len(kits)} kits)\n\n")
        f.write("# === INDIVIDUAL PRODUCTS ===\n")
        for url in individual:
            f.write(url + "\n")
        f.write(f"\n# === KITS ({len(kits)}) ===\n")
        for url in kits:
            f.write(url + "\n")
    logger.info(f"Saved URL list to {url_file}")

    if args.discover_only:
        logger.info("--discover-only: stopping here.")
        return

    # ── Phase 2: Extract ──
    engine = get_engine()
    with Session(engine) as session:
        existing_urls = set(
            r[0]
            for r in session.query(ProductORM.product_url)
            .filter(ProductORM.brand_slug == BRAND)
            .all()
        )
        new_urls = sorted(all_urls - existing_urls)

        logger.info(f"\n{'=' * 60}")
        logger.info(f"PHASE 2: Extracting {len(new_urls)} new products ({len(existing_urls)} already in DB)...")
        logger.info(f"{'=' * 60}")

        if not new_urls:
            logger.info("Nothing new to extract!")
        else:
            browser = BrowserClient(headless=True, delay_seconds=1.5)
            try:
                stats = extract_products(new_urls, session, browser)
                logger.info(f"\nExtraction results: {stats}")
            finally:
                browser.close()

        # ── Phase 3: Coverage ──
        logger.info(f"\n{'=' * 60}")
        logger.info("PHASE 3: Updating coverage stats...")
        logger.info(f"{'=' * 60}")
        update_coverage(session)

        # Final summary
        final = session.query(ProductORM).filter(ProductORM.brand_slug == BRAND).count()
        verified = (
            session.query(ProductORM)
            .filter(ProductORM.brand_slug == BRAND, ProductORM.verification_status == "verified_inci")
            .count()
        )
        logger.info(f"\n{'=' * 60}")
        logger.info(f"FINAL: {final} products total, {verified} verified INCI")
        logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
