"""Re-fetch INCI ingredients for Amend products that are missing them.
Targets individual (non-kit) products without INCI data."""
from __future__ import annotations

import json
import logging
import sys
import time

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from src.core.browser import BrowserClient
from src.core.qa_gate import run_product_qa
from src.core.models import ProductExtraction, GenderTarget
from src.core.taxonomy import normalize_product_type, normalize_category
from src.extraction.deterministic import extract_product_deterministic
from src.extraction.inci_extractor import extract_and_validate_inci
from src.storage.database import get_engine
from src.storage.orm_models import ProductORM

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BRAND = "amend"


def _extract_first_inci_block(text: str) -> str:
    """If text has multiple concatenated INCI lists, extract only the first one.

    Some Amend pages list INCI for multiple products:
    'Shampoo: Aqua, X, Y. Condicionador: Aqua, Z, W'
    We take only the first block up to the second 'Aqua' occurrence.
    """
    import re
    # Find all positions of Aqua/Water
    positions = [m.start() for m in re.finditer(r'\bAqua\b|\bWater\b', text, re.IGNORECASE)]
    if len(positions) >= 2:
        # Cut before the second Aqua, then trim back to last separator
        cut_point = positions[1]
        first_block = text[:cut_point].rstrip()
        # Remove trailing product heading like "Condicionador:"
        first_block = re.sub(r'[A-ZÀ-Ú][a-zà-ú]+(\s+[A-ZÀ-Ú]?[a-zà-ú]*)*\s*:\s*$', '', first_block).rstrip(' ,.')
        return first_block
    return text


def extract_amend_inci(html: str) -> str | None:
    """Extract INCI from Amend's specific HTML structure.

    Amend uses multiple .greyBackground sections. The INCI list is in the one
    with a <b class="sub-title">TODOS</b> heading.
    """
    soup = BeautifulSoup(html, "lxml")

    # Strategy 1: Find the greyBackground with "TODOS" subtitle
    for grey in soup.select(".greyBackground"):
        subtitle = grey.find("b", class_="sub-title")
        if subtitle and subtitle.get_text(strip=True).upper() == "TODOS":
            p = grey.find("p", class_="description-product-page")
            if p:
                text = p.get_text(strip=True)
                if text and len(text) > 20 and "," in text:
                    return _extract_first_inci_block(text)

    # Strategy 2: Look for ingredients-content that's not empty
    ic = soup.find(class_="ingredients-content")
    if ic:
        text = ic.get_text(strip=True)
        if text and len(text) > 20 and "," in text:
            return _extract_first_inci_block(text)

    # Strategy 3: Find any greyBackground with comma-separated chemical names
    for grey in soup.select(".greyBackground"):
        for p in grey.find_all("p", class_="description-product-page"):
            text = p.get_text(strip=True)
            if text and len(text) > 50 and "," in text and "Aqua" in text:
                return _extract_first_inci_block(text)

    return None


def get_products_missing_inci(session: Session, include_kits: bool = False) -> list[ProductORM]:
    """Find products with no INCI ingredients."""
    query = session.query(ProductORM).filter(
        ProductORM.brand_slug == BRAND,
        ProductORM.verification_status != "quarantined",
    )
    if not include_kits:
        query = query.filter(ProductORM.is_kit == False)

    products = query.all()
    missing = []
    for p in products:
        inci = p.inci_ingredients
        if isinstance(inci, str):
            inci = json.loads(inci) if inci else []
        if not inci:
            missing.append(p)
    return missing


def refetch_inci(session: Session, browser: BrowserClient, products: list[ProductORM]) -> dict:
    """Re-fetch pages and extract INCI for each product."""
    stats = {"total": len(products), "found": 0, "verified": 0, "not_found": 0, "failed": 0}

    for i, p in enumerate(products, 1):
        logger.info(f"[{i}/{len(products)}] {p.product_name[:60]}")
        try:
            html = browser.fetch_page(p.product_url)

            # Use Amend-specific INCI extraction
            inci_raw = extract_amend_inci(html)

            if not inci_raw:
                logger.info(f"  -> No INCI found on page")
                stats["not_found"] += 1
                continue

            inci_result = extract_and_validate_inci(inci_raw)
            if inci_result.valid and inci_result.cleaned:
                p.inci_ingredients = inci_result.cleaned
                p.verification_status = "verified_inci"
                p.confidence = max(p.confidence, 0.85)
                stats["found"] += 1
                stats["verified"] += 1
                logger.info(f"  -> VERIFIED: {len(inci_result.cleaned)} ingredients")
            else:
                logger.info(f"  -> INCI found but validation failed: {inci_result.rejection_reason}")
                stats["not_found"] += 1

        except Exception as e:
            logger.error(f"  -> FAILED: {e}")
            stats["failed"] += 1

    return stats


def main():
    engine = get_engine()
    with Session(engine) as session:
        missing = get_products_missing_inci(session, include_kits=False)
        logger.info(f"Found {len(missing)} individual products without INCI")

        if not missing:
            logger.info("Nothing to do!")
            return

        browser = BrowserClient(headless=True, delay_seconds=2)
        try:
            stats = refetch_inci(session, browser, missing)
            session.commit()
        finally:
            browser.close()

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"RESULTS:")
        logger.info(f"  Total processed: {stats['total']}")
        logger.info(f"  INCI found & verified: {stats['verified']}")
        logger.info(f"  INCI not found: {stats['not_found']}")
        logger.info(f"  Failed (error): {stats['failed']}")
        logger.info("=" * 60)

        # Updated counts
        total = session.query(ProductORM).filter(
            ProductORM.brand_slug == BRAND, ProductORM.is_kit == False
        ).count()
        still_missing = len(get_products_missing_inci(session, include_kits=False))
        logger.info(f"\nIndividuais: {total} total, {total - still_missing} com INCI, {still_missing} ainda sem")


if __name__ == "__main__":
    main()
