#!/usr/bin/env python3
"""Migrate brand data from local SQLite (haira.db) to per-brand PostgreSQL on Railway.

Usage:
    python3 scripts/migrate_to_railway.py --brand <slug>
    python3 scripts/migrate_to_railway.py --all
    python3 scripts/migrate_to_railway.py --brand <slug> --source sqlite:///haira.db
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import pathlib
from typing import Any

# Ensure project root is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _get_central_url() -> str:
    return _normalise_url(
        os.environ.get("CENTRAL_DATABASE_URL", "sqlite:///haira_central.db")
    )


def _get_brand_db_url(brand_slug: str, central_session: Session) -> str | None:
    from src.storage.central_models import BrandDatabaseORM  # noqa: PLC0415

    brand = (
        central_session.query(BrandDatabaseORM)
        .filter(BrandDatabaseORM.brand_slug == brand_slug)
        .first()
    )
    if brand is None:
        logger.error("Brand '%s' not found in central DB.", brand_slug)
        return None
    if not brand.is_active:
        logger.warning("Brand '%s' is marked inactive. Skipping.", brand_slug)
        return None
    return _normalise_url(brand.database_url)


# ---------------------------------------------------------------------------
# Core migration logic
# ---------------------------------------------------------------------------

def _migrate_brand(
    brand_slug: str,
    source_session: Session,
    dest_session: Session,
) -> dict[str, int]:
    """Migrate all tables for a single brand. Returns a counts dict."""
    from src.storage.orm_models import (  # noqa: PLC0415
        ProductORM,
        ProductEvidenceORM,
        QuarantineDetailORM,
        BrandCoverageORM,
        IngredientORM,
        IngredientAliasORM,
        ProductIngredientORM,
        ClaimORM,
        ClaimAliasORM,
        ProductClaimORM,
        ProductImageORM,
        ProductCompositionORM,
        ValidationComparisonORM,
        ReviewQueueORM,
    )

    counts: dict[str, int] = {}

    # 1. Products (filter by brand_slug)
    products = (
        source_session.query(ProductORM)
        .filter(ProductORM.brand_slug == brand_slug)
        .all()
    )
    product_ids = [p.id for p in products]
    logger.info("[%s] Migrating %d products...", brand_slug, len(products))
    for obj in products:
        dest_session.merge(obj)
    counts["products"] = len(products)

    if not product_ids:
        dest_session.commit()
        return counts

    # Helper: query by product_id IN list, chunked
    def _by_product_ids(model: Any, field: str = "product_id") -> list[Any]:
        rows = []
        chunk_size = 500
        for i in range(0, len(product_ids), chunk_size):
            chunk = product_ids[i : i + chunk_size]
            rows.extend(
                source_session.query(model)
                .filter(getattr(model, field).in_(chunk))
                .all()
            )
        return rows

    # 2. ProductEvidence
    evidence_rows = _by_product_ids(ProductEvidenceORM)
    logger.info("[%s] Migrating %d evidence rows...", brand_slug, len(evidence_rows))
    for obj in evidence_rows:
        dest_session.merge(obj)
    counts["product_evidence"] = len(evidence_rows)

    # 3. QuarantineDetail
    qd_rows = _by_product_ids(QuarantineDetailORM)
    logger.info("[%s] Migrating %d quarantine rows...", brand_slug, len(qd_rows))
    for obj in qd_rows:
        dest_session.merge(obj)
    counts["quarantine_details"] = len(qd_rows)

    # 4. BrandCoverage
    coverage_rows = (
        source_session.query(BrandCoverageORM)
        .filter(BrandCoverageORM.brand_slug == brand_slug)
        .all()
    )
    logger.info("[%s] Migrating %d coverage rows...", brand_slug, len(coverage_rows))
    for obj in coverage_rows:
        dest_session.merge(obj)
    counts["brand_coverage"] = len(coverage_rows)

    # 5. ProductIngredient (by product_id) + referenced Ingredients + Aliases
    pi_rows = _by_product_ids(ProductIngredientORM)
    ingredient_ids = list({pi.ingredient_id for pi in pi_rows})

    ingredients: list[IngredientORM] = []
    aliases: list[IngredientAliasORM] = []
    chunk_size = 500
    for i in range(0, len(ingredient_ids), chunk_size):
        chunk = ingredient_ids[i : i + chunk_size]
        ingredients.extend(
            source_session.query(IngredientORM)
            .filter(IngredientORM.id.in_(chunk))
            .all()
        )
        aliases.extend(
            source_session.query(IngredientAliasORM)
            .filter(IngredientAliasORM.ingredient_id.in_(chunk))
            .all()
        )

    logger.info(
        "[%s] Migrating %d ingredients, %d aliases, %d product_ingredients...",
        brand_slug, len(ingredients), len(aliases), len(pi_rows),
    )
    for obj in ingredients:
        dest_session.merge(obj)
    for obj in aliases:
        dest_session.merge(obj)
    for obj in pi_rows:
        dest_session.merge(obj)
    counts["ingredients"] = len(ingredients)
    counts["ingredient_aliases"] = len(aliases)
    counts["product_ingredients"] = len(pi_rows)

    # 6. ProductClaim (by product_id) + referenced Claims + ClaimAliases
    pc_rows = _by_product_ids(ProductClaimORM)
    claim_ids = list({pc.claim_id for pc in pc_rows})

    claims: list[ClaimORM] = []
    claim_aliases: list[ClaimAliasORM] = []
    for i in range(0, len(claim_ids), chunk_size):
        chunk = claim_ids[i : i + chunk_size]
        claims.extend(
            source_session.query(ClaimORM)
            .filter(ClaimORM.id.in_(chunk))
            .all()
        )
        claim_aliases.extend(
            source_session.query(ClaimAliasORM)
            .filter(ClaimAliasORM.claim_id.in_(chunk))
            .all()
        )

    logger.info(
        "[%s] Migrating %d claims, %d claim_aliases, %d product_claims...",
        brand_slug, len(claims), len(claim_aliases), len(pc_rows),
    )
    for obj in claims:
        dest_session.merge(obj)
    for obj in claim_aliases:
        dest_session.merge(obj)
    for obj in pc_rows:
        dest_session.merge(obj)
    counts["claims"] = len(claims)
    counts["claim_aliases"] = len(claim_aliases)
    counts["product_claims"] = len(pc_rows)

    # 7. ProductImages
    image_rows = _by_product_ids(ProductImageORM)
    logger.info("[%s] Migrating %d image rows...", brand_slug, len(image_rows))
    for obj in image_rows:
        dest_session.merge(obj)
    counts["product_images"] = len(image_rows)

    # 8. ProductCompositions
    comp_rows = _by_product_ids(ProductCompositionORM)
    logger.info("[%s] Migrating %d composition rows...", brand_slug, len(comp_rows))
    for obj in comp_rows:
        dest_session.merge(obj)
    counts["product_compositions"] = len(comp_rows)

    # 9. ValidationComparisons
    vc_rows = _by_product_ids(ValidationComparisonORM)
    logger.info("[%s] Migrating %d validation_comparison rows...", brand_slug, len(vc_rows))
    for obj in vc_rows:
        dest_session.merge(obj)
    counts["validation_comparisons"] = len(vc_rows)

    # 10. ReviewQueue (depends on validation_comparisons existing)
    rq_rows = _by_product_ids(ReviewQueueORM)
    logger.info("[%s] Migrating %d review_queue rows...", brand_slug, len(rq_rows))
    for obj in rq_rows:
        dest_session.merge(obj)
    counts["review_queue"] = len(rq_rows)

    dest_session.commit()
    return counts


def _update_central_stats(
    brand_slug: str,
    central_session: Session,
    counts: dict[str, int],
) -> None:
    from src.storage.central_models import BrandDatabaseORM  # noqa: PLC0415

    brand = (
        central_session.query(BrandDatabaseORM)
        .filter(BrandDatabaseORM.brand_slug == brand_slug)
        .first()
    )
    if brand is None:
        return

    product_count = counts.get("products", 0)
    brand.product_count = product_count

    # Approximate inci_rate: products with inci_ingredients not null / total
    # We don't have that data directly in counts, leave inci_rate alone if no
    # products were migrated.
    if product_count > 0:
        from src.storage.orm_models import ProductORM  # noqa: PLC0415
        # Use the dest session to query inci count — caller must provide it
        # Instead, set to 0.0 as a safe default; real value updated by haira audit
        pass

    central_session.add(brand)
    central_session.commit()
    logger.info(
        "[%s] Central DB updated: product_count=%d",
        brand_slug,
        product_count,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate brand data from local SQLite to per-brand databases on Railway."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--brand", metavar="SLUG", help="Single brand slug to migrate.")
    group.add_argument("--all", action="store_true", help="Migrate all active brands.")
    parser.add_argument(
        "--source",
        default="sqlite:///haira.db",
        help="Source SQLite URL (default: sqlite:///haira.db).",
    )
    args = parser.parse_args()

    source_url = _normalise_url(args.source)
    logger.info("Source DB: %s", source_url)

    source_engine = create_engine(source_url)
    central_url = _get_central_url()
    central_engine = create_engine(central_url)

    with Session(source_engine) as source_session, Session(central_engine) as central_session:
        from src.storage.central_models import BrandDatabaseORM  # noqa: PLC0415

        if args.all:
            brands = (
                central_session.query(BrandDatabaseORM)
                .filter(BrandDatabaseORM.is_active == True)  # noqa: E712
                .all()
            )
            slugs = [b.brand_slug for b in brands]
        else:
            slugs = [args.brand]

        if not slugs:
            logger.info("No brands to migrate.")
            return

        overall_success = 0
        overall_failure = 0

        for slug in slugs:
            dest_url = _get_brand_db_url(slug, central_session)
            if dest_url is None:
                overall_failure += 1
                continue

            logger.info("=== Migrating brand: %s ===", slug)
            dest_engine = create_engine(dest_url)

            try:
                with Session(dest_engine) as dest_session:
                    counts = _migrate_brand(slug, source_session, dest_session)
                _update_central_stats(slug, central_session, counts)
                logger.info("[%s] Migration complete. Counts: %s", slug, counts)
                overall_success += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("[%s] Migration FAILED: %s", slug, exc, exc_info=True)
                overall_failure += 1
            finally:
                dest_engine.dispose()

    logger.info(
        "Done. Succeeded: %d, Failed: %d", overall_success, overall_failure
    )

    if overall_failure > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
