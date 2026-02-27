#!/usr/bin/env python3
"""
Amend gap-fill script:
1. Remove discontinued products (old URLs not on current site)
2. Extract 17 missing products from amend.com.br
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.browser import BrowserClient
from src.core.models import ProductExtraction, GenderTarget
from src.core.qa_gate import run_product_qa
from src.core.taxonomy import normalize_product_type, detect_gender_target, is_hair_relevant_by_keywords
from src.extraction.deterministic import extract_product_deterministic
from src.extraction.inci_extractor import extract_and_validate_inci
from src.storage.database import get_engine
from src.storage.orm_models import ProductORM, ProductEvidenceORM, QuarantineDetailORM, BrandCoverageORM
from src.storage.repository import ProductRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BRAND = "amend"
ALLOWED_DOMAINS = ["www.amend.com.br"]

# Selectors from amend.yaml blueprint
INCI_SELECTORS = [
    ".product-ingredients p", ".product-ingredients",
    "#ingredientes p", "#composicao p",
    '[data-tab="ingredientes"] p', ".product-description p",
]
NAME_SELECTORS = ["h1.product-name", "h1", ".product-title", ".product-name"]

# 17 missing individual product URLs (non-kit)
MISSING_URLS = [
    "https://www.amend.com.br/acidificante-mascara-de-equilibrio-do-ph-amend-essencial/p/1390-1.html",
    "https://www.amend.com.br/amend-hidrata-mascara-hidratante-efeito-imediato/p/1610-1.html",
    "https://www.amend.com.br/coloracao-amend-color-intensy-6.34-louro-escuro-dourado-acobreado-50g/p/994-1.html",
    "https://www.amend.com.br/condicionador-amend-expertise-hidratacao-e-forca/p/1368-1.html",
    "https://www.amend.com.br/condicionador-amend-gold-black-hidratacao-nutritiva/p/1605-1.html",
    "https://www.amend.com.br/condicionador-doador-de-volume-amend-expertise-volume-absoluto/p/1397-1.html",
    "https://www.amend.com.br/creme-para-pentear-amend-gold-black-hidratacao-nutritiva/p/1607-1.html",
    "https://www.amend.com.br/gelatina-modeladora-de-cachos-amend-gold-black-hidratacao-nutritiva/p/1608-1.html",
    "https://www.amend.com.br/mascara-amend-millenar-oleos-japoneses/p/1385-1.html",
    "https://www.amend.com.br/mascara-doadora-de-volume-amend-expertise-volume-absoluto/p/1398-1.html",
    "https://www.amend.com.br/mascara-restauradora-amend-gold-black-hidratacao-nutritiva/p/1606-1.html",
    "https://www.amend.com.br/rmc-system-%7C-sistema-integrado-repositor-de-massa-capilar/p/1136-1.html",
    "https://www.amend.com.br/shampoo-amend-expertise-hidratacao-e-forca/p/1367-1.html",
    "https://www.amend.com.br/shampoo-amend-gold-black-hidratacao-nutritiva/p/1604-1.html",
    "https://www.amend.com.br/shampoo-amend-millenar-oleos-japoneses/p/1383-1.html",
    "https://www.amend.com.br/shampoo-equilibrante-amend-expertise-oleosidade-equilibrada/p/1377-1.html",
    "https://www.amend.com.br/amend-gold-black-kit-rmc-system-q%2B/p/462-1.html",
]

# Current site product URLs (non-kit) — products that should remain
CURRENT_SITE_URLS = {
    "https://www.amend.com.br/acidificante-mascara-de-equilibrio-do-ph-amend-essencial/p/1390-1.html",
    "https://www.amend.com.br/amend-essencial-cronograma-capilar-superdoses-de-reparacao/p/1379-1.html",
    "https://www.amend.com.br/amend-essencial-seca-sem-frizz/p/1387-1.html",
    "https://www.amend.com.br/amend-gold-black-kit-rmc-system-q%2B/p/462-1.html",
    "https://www.amend.com.br/amend-hidrata-mascara-hidratante-efeito-imediato/p/1610-1.html",
    "https://www.amend.com.br/amend-matiza-mascara-matizadora-efeito-imediato/p/1612-1.html",
    "https://www.amend.com.br/amend-nutre-mascara-nutritiva-efeito-imediato/p/1611-1.html",
    "https://www.amend.com.br/amend-reconstroi-mascara-reparadora-efeito-imediato/p/1609-1.html",
    "https://www.amend.com.br/balm-selante-amend-millenar-oleos-japoneses/p/1386-1.html",
    "https://www.amend.com.br/coloracao-amend-color-intensy-6.34-louro-escuro-dourado-acobreado-50g/p/994-1.html",
    "https://www.amend.com.br/condicionador-amend-expertise-hidratacao-e-forca/p/1368-1.html",
    "https://www.amend.com.br/condicionador-amend-gold-black-hidratacao-nutritiva/p/1605-1.html",
    "https://www.amend.com.br/condicionador-amend-millenar-oleos-japoneses/p/1384-1.html",
    "https://www.amend.com.br/condicionador-doador-de-volume-amend-expertise-volume-absoluto/p/1397-1.html",
    "https://www.amend.com.br/condicionador-equilibrante-amend-expertise-oleosidade-equilibrada/p/1378-1.html",
    "https://www.amend.com.br/creme-para-pentear-amend-gold-black-hidratacao-nutritiva/p/1607-1.html",
    "https://www.amend.com.br/fluido-antiumidade-amend-blindagem-essencial/p/1366-1.html",
    "https://www.amend.com.br/fluido-restaurador-amend-essencial-multibeneficios/p/1365-1.html",
    "https://www.amend.com.br/gelatina-modeladora-de-cachos-amend-gold-black-hidratacao-nutritiva/p/1608-1.html",
    "https://www.amend.com.br/leave-in-amend-expertise-hidratacao-e-forca/p/1370-1.html",
    "https://www.amend.com.br/mascara-amend-expertise-hidratacao-e-forca/p/1369-1.html",
    "https://www.amend.com.br/mascara-amend-millenar-oleos-japoneses/p/1385-1.html",
    "https://www.amend.com.br/mascara-condicionante-duplo-efeito-amend-essencial-antiqueda/p/1601-1.html",
    "https://www.amend.com.br/mascara-doadora-de-volume-amend-expertise-volume-absoluto/p/1398-1.html",
    "https://www.amend.com.br/mascara-restauradora-amend-gold-black-hidratacao-nutritiva/p/1606-1.html",
    "https://www.amend.com.br/mousse-doadora-de-volume-amend-expertise-volume-absoluto/p/1399-1.html",
    "https://www.amend.com.br/rmc-system-%7C-sistema-integrado-repositor-de-massa-capilar/p/1136-1.html",
    "https://www.amend.com.br/serum-pro-volume-amend-essencial-antiqueda/p/1603-1.html",
    "https://www.amend.com.br/shampoo-amend-expertise-hidratacao-e-forca/p/1367-1.html",
    "https://www.amend.com.br/shampoo-amend-gold-black-hidratacao-nutritiva/p/1604-1.html",
    "https://www.amend.com.br/shampoo-amend-millenar-oleos-japoneses/p/1383-1.html",
    "https://www.amend.com.br/shampoo-amend-millenar-oleos-japoneses/p/1383-1.html",
    "https://www.amend.com.br/shampoo-doador-de-volume-amend-expertise-volume-absoluto/p/1396-1.html",
    "https://www.amend.com.br/shampoo-equilibrante-amend-expertise-oleosidade-equilibrada/p/1377-1.html",
    "https://www.amend.com.br/shampoo-fortificante-amend-essencial-antiqueda/p/1600-1.html",
    "https://www.amend.com.br/tonico-estimulante-do-crescimento-amend-essencial-antiqueda/p/1602-1.html",
}


def remove_discontinued(session: Session) -> int:
    """Remove products whose URLs are no longer on the current Amend site."""
    products = session.query(ProductORM).filter(ProductORM.brand_slug == BRAND).all()
    removed = 0
    for p in products:
        if p.product_url not in CURRENT_SITE_URLS:
            # Delete evidence first (FK constraint)
            session.query(ProductEvidenceORM).filter(
                ProductEvidenceORM.product_id == p.id
            ).delete(synchronize_session=False)
            # Delete quarantine if exists
            session.query(QuarantineDetailORM).filter(
                QuarantineDetailORM.product_id == p.id
            ).delete(synchronize_session=False)
            session.delete(p)
            logger.info(f"  Removed: {p.product_name[:60]} ({p.product_url})")
            removed += 1
    session.flush()
    return removed


def extract_missing(session: Session, browser: BrowserClient) -> dict:
    """Extract the 17 missing products."""
    repo = ProductRepository(session)
    stats = {"extracted": 0, "verified": 0, "catalog": 0, "failed": 0}

    # Skip URLs already in DB
    existing_urls = set(
        r[0] for r in session.query(ProductORM.product_url)
        .filter(ProductORM.brand_slug == BRAND)
        .all()
    )

    urls_to_extract = [u for u in MISSING_URLS if u not in existing_urls]
    logger.info(f"URLs to extract: {len(urls_to_extract)} (skipping {len(MISSING_URLS) - len(urls_to_extract)} already in DB)")

    for i, url in enumerate(urls_to_extract, 1):
        logger.info(f"[{i}/{len(urls_to_extract)}] Extracting: {url}")
        try:
            html = browser.fetch_page(url)

            det_result = extract_product_deterministic(
                html=html, url=url,
                inci_selectors=INCI_SELECTORS,
                name_selectors=NAME_SELECTORS,
            )

            product_name = det_result.get("product_name") or ""
            if not product_name:
                logger.warning(f"  No product name found, skipping")
                stats["failed"] += 1
                continue

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
                gender_target=GenderTarget(gender) if gender in [e.value for e in GenderTarget] else GenderTarget.UNKNOWN,
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
            stats["extracted"] += 1

            if qa_result.status.value == "verified_inci":
                stats["verified"] += 1
                logger.info(f"  VERIFIED: {product_name[:50]} ({len(inci_list or [])} INCI)")
            elif qa_result.status.value == "catalog_only":
                stats["catalog"] += 1
                logger.info(f"  CATALOG: {product_name[:50]}")
            else:
                logger.info(f"  QUARANTINED: {product_name[:50]} - {qa_result.rejection_reason}")

        except Exception as e:
            logger.error(f"  FAILED: {url} - {e}")
            stats["failed"] += 1

    return stats


def update_coverage(session: Session):
    """Update brand coverage stats."""
    products = session.query(ProductORM).filter(ProductORM.brand_slug == BRAND).all()
    total = len(products)
    verified = sum(1 for p in products if p.verification_status == "verified_inci")
    catalog = sum(1 for p in products if p.verification_status == "catalog_only")
    quarantined = sum(1 for p in products if p.verification_status == "quarantined")
    rate = verified / total if total > 0 else 0.0

    coverage = session.query(BrandCoverageORM).filter(
        BrandCoverageORM.brand_slug == BRAND
    ).first()
    if coverage:
        coverage.extracted_total = total
        coverage.verified_inci_total = verified
        coverage.verified_inci_rate = rate
        coverage.catalog_only_total = catalog
        coverage.quarantined_total = quarantined
        coverage.updated_at = datetime.now(timezone.utc)
        logger.info(f"Coverage updated: {total} extracted, {verified} verified ({rate:.1%})")


def main():
    engine = get_engine()
    with Session(engine) as session:
        # Step 1: Remove discontinued products
        logger.info("=" * 60)
        logger.info("STEP 1: Removing discontinued products...")
        logger.info("=" * 60)
        removed = remove_discontinued(session)
        logger.info(f"Removed {removed} discontinued products")
        session.commit()

        # Remaining count
        remaining = session.query(ProductORM).filter(ProductORM.brand_slug == BRAND).count()
        logger.info(f"Remaining products in DB: {remaining}")

        # Step 2: Extract missing products
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 2: Extracting missing products...")
        logger.info("=" * 60)
        browser = BrowserClient(headless=True, delay_seconds=2)
        try:
            stats = extract_missing(session, browser)
            session.commit()
        finally:
            browser.close()

        logger.info(f"\nExtraction results: {stats}")

        # Step 3: Update coverage
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 3: Updating coverage stats...")
        logger.info("=" * 60)
        update_coverage(session)
        session.commit()

        # Final summary
        final_count = session.query(ProductORM).filter(ProductORM.brand_slug == BRAND).count()
        final_verified = session.query(ProductORM).filter(
            ProductORM.brand_slug == BRAND,
            ProductORM.verification_status == "verified_inci"
        ).count()
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"FINAL: {final_count} products, {final_verified} verified INCI")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
