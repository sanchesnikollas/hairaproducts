#!/usr/bin/env python3
"""Fast migration: SQLite → Railway PostgreSQL using bulk inserts.

Since target DBs are fresh (just created), we skip merge() and use
bulk_save_objects() with batched commits for 10-50x speedup.

Usage:
    CENTRAL_DATABASE_URL=... python3 scripts/migrate_to_railway_fast.py --all
    CENTRAL_DATABASE_URL=... python3 scripts/migrate_to_railway_fast.py --brand amend
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import pathlib
import time
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session, make_transient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 200


def _normalise_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _get_central_url() -> str:
    return _normalise_url(
        os.environ.get("CENTRAL_DATABASE_URL", "sqlite:///haira_central.db")
    )


def _bulk_copy(
    source_session: Session,
    dest_engine,
    model: Any,
    filters: list | None = None,
    label: str = "",
) -> int:
    """Copy all rows matching filters from source to dest using bulk insert."""
    query = source_session.query(model)
    if filters:
        for f in filters:
            query = query.filter(f)
    rows = query.all()
    count = len(rows)

    if count == 0:
        logger.info("  %s: 0 rows", label)
        return 0

    # Detach from source session and make transient
    for r in rows:
        source_session.expunge(r)
        make_transient(r)

    # Bulk insert in batches
    with Session(dest_engine) as dest_session:
        for i in range(0, count, BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            dest_session.add_all(batch)
            dest_session.flush()
        dest_session.commit()

    logger.info("  %s: %d rows", label, count)
    return count


def _migrate_brand(
    brand_slug: str,
    source_engine,
    dest_url: str,
) -> dict[str, int]:
    """Migrate all tables for a single brand using bulk inserts."""
    from src.storage.orm_models import (
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

    dest_engine = create_engine(dest_url, pool_pre_ping=True)
    counts: dict[str, int] = {}
    t0 = time.time()

    with Session(source_engine) as src:
        # 1. Products
        products = src.query(ProductORM).filter(ProductORM.brand_slug == brand_slug).all()
        product_ids = [p.id for p in products]
        for p in products:
            src.expunge(p)
            make_transient(p)

        with Session(dest_engine) as dest:
            for i in range(0, len(products), BATCH_SIZE):
                dest.add_all(products[i : i + BATCH_SIZE])
                dest.flush()
            dest.commit()
        counts["products"] = len(products)
        logger.info("  products: %d", len(products))

        if not product_ids:
            dest_engine.dispose()
            return counts

        # Helper: query rows by product_id chunks
        def _get_by_product_ids(model, field="product_id"):
            rows = []
            for i in range(0, len(product_ids), 500):
                chunk = product_ids[i : i + 500]
                rows.extend(
                    src.query(model).filter(getattr(model, field).in_(chunk)).all()
                )
            for r in rows:
                src.expunge(r)
                make_transient(r)
            return rows

        # 2. Evidence
        evidence = _get_by_product_ids(ProductEvidenceORM)
        with Session(dest_engine) as dest:
            for i in range(0, len(evidence), BATCH_SIZE):
                dest.add_all(evidence[i : i + BATCH_SIZE])
                dest.flush()
            dest.commit()
        counts["evidence"] = len(evidence)
        logger.info("  evidence: %d", len(evidence))

        # 3. Quarantine
        qd = _get_by_product_ids(QuarantineDetailORM)
        with Session(dest_engine) as dest:
            dest.add_all(qd)
            dest.commit()
        counts["quarantine"] = len(qd)
        logger.info("  quarantine: %d", len(qd))

        # 4. Coverage
        coverage = src.query(BrandCoverageORM).filter(BrandCoverageORM.brand_slug == brand_slug).all()
        for r in coverage:
            src.expunge(r)
            make_transient(r)
        with Session(dest_engine) as dest:
            dest.add_all(coverage)
            dest.commit()
        counts["coverage"] = len(coverage)
        logger.info("  coverage: %d", len(coverage))

        # 5. ProductIngredients -> need Ingredients first
        pi_rows = _get_by_product_ids(ProductIngredientORM)
        ingredient_ids = list({pi.ingredient_id for pi in pi_rows})

        ingredients = []
        aliases = []
        for i in range(0, len(ingredient_ids), 500):
            chunk = ingredient_ids[i : i + 500]
            ingredients.extend(src.query(IngredientORM).filter(IngredientORM.id.in_(chunk)).all())
            aliases.extend(src.query(IngredientAliasORM).filter(IngredientAliasORM.ingredient_id.in_(chunk)).all())

        for r in ingredients:
            src.expunge(r)
            make_transient(r)
        for r in aliases:
            src.expunge(r)
            make_transient(r)

        with Session(dest_engine) as dest:
            for i in range(0, len(ingredients), BATCH_SIZE):
                dest.add_all(ingredients[i : i + BATCH_SIZE])
                dest.flush()
            dest.commit()
        counts["ingredients"] = len(ingredients)
        logger.info("  ingredients: %d", len(ingredients))

        with Session(dest_engine) as dest:
            for i in range(0, len(aliases), BATCH_SIZE):
                dest.add_all(aliases[i : i + BATCH_SIZE])
                dest.flush()
            dest.commit()
        counts["aliases"] = len(aliases)
        logger.info("  ingredient_aliases: %d", len(aliases))

        with Session(dest_engine) as dest:
            for i in range(0, len(pi_rows), BATCH_SIZE):
                dest.add_all(pi_rows[i : i + BATCH_SIZE])
                dest.flush()
            dest.commit()
        counts["product_ingredients"] = len(pi_rows)
        logger.info("  product_ingredients: %d", len(pi_rows))

        # 6. Claims
        pc_rows = _get_by_product_ids(ProductClaimORM)
        claim_ids = list({pc.claim_id for pc in pc_rows})

        claims = []
        claim_aliases = []
        for i in range(0, len(claim_ids), 500):
            chunk = claim_ids[i : i + 500]
            claims.extend(src.query(ClaimORM).filter(ClaimORM.id.in_(chunk)).all())
            claim_aliases.extend(src.query(ClaimAliasORM).filter(ClaimAliasORM.claim_id.in_(chunk)).all())

        for r in claims:
            src.expunge(r)
            make_transient(r)
        for r in claim_aliases:
            src.expunge(r)
            make_transient(r)

        with Session(dest_engine) as dest:
            for i in range(0, len(claims), BATCH_SIZE):
                dest.add_all(claims[i : i + BATCH_SIZE])
                dest.flush()
            dest.commit()
        counts["claims"] = len(claims)
        logger.info("  claims: %d", len(claims))

        with Session(dest_engine) as dest:
            dest.add_all(claim_aliases)
            dest.commit()
        counts["claim_aliases"] = len(claim_aliases)
        logger.info("  claim_aliases: %d", len(claim_aliases))

        with Session(dest_engine) as dest:
            for i in range(0, len(pc_rows), BATCH_SIZE):
                dest.add_all(pc_rows[i : i + BATCH_SIZE])
                dest.flush()
            dest.commit()
        counts["product_claims"] = len(pc_rows)
        logger.info("  product_claims: %d", len(pc_rows))

        # 7. Images
        images = _get_by_product_ids(ProductImageORM)
        with Session(dest_engine) as dest:
            for i in range(0, len(images), BATCH_SIZE):
                dest.add_all(images[i : i + BATCH_SIZE])
                dest.flush()
            dest.commit()
        counts["images"] = len(images)
        logger.info("  images: %d", len(images))

        # 8. Compositions
        comps = _get_by_product_ids(ProductCompositionORM)
        with Session(dest_engine) as dest:
            dest.add_all(comps)
            dest.commit()
        counts["compositions"] = len(comps)
        logger.info("  compositions: %d", len(comps))

        # 9. ValidationComparisons
        vc = _get_by_product_ids(ValidationComparisonORM)
        with Session(dest_engine) as dest:
            dest.add_all(vc)
            dest.commit()
        counts["validation_comparisons"] = len(vc)
        logger.info("  validation_comparisons: %d", len(vc))

        # 10. ReviewQueue
        rq = _get_by_product_ids(ReviewQueueORM)
        with Session(dest_engine) as dest:
            dest.add_all(rq)
            dest.commit()
        counts["review_queue"] = len(rq)
        logger.info("  review_queue: %d", len(rq))

    elapsed = time.time() - t0
    logger.info("[%s] Done in %.1fs. Total rows: %d", brand_slug, elapsed, sum(counts.values()))
    dest_engine.dispose()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--brand", metavar="SLUG")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--source", default="sqlite:///haira.db")
    args = parser.parse_args()

    source_url = _normalise_url(args.source)
    source_engine = create_engine(source_url)
    central_url = _get_central_url()
    central_engine = create_engine(central_url)

    from src.storage.central_models import BrandDatabaseORM

    with Session(central_engine) as central:
        if args.all:
            brands = central.query(BrandDatabaseORM).filter(BrandDatabaseORM.is_active == True).all()
        else:
            brands = central.query(BrandDatabaseORM).filter(BrandDatabaseORM.brand_slug == args.brand).all()

        if not brands:
            logger.info("No brands found.")
            return

        success = 0
        failure = 0

        for brand in brands:
            slug = brand.brand_slug
            dest_url = _normalise_url(brand.database_url)
            logger.info("=== %s ===", slug)

            try:
                # Check if already has data (skip if so)
                dest_engine = create_engine(dest_url)
                with Session(dest_engine) as check:
                    from src.storage.orm_models import ProductORM
                    existing = check.query(ProductORM).limit(1).first()
                    if existing:
                        logger.info("[%s] Already has data, skipping.", slug)
                        dest_engine.dispose()
                        success += 1
                        continue
                dest_engine.dispose()

                counts = _migrate_brand(slug, source_engine, dest_url)

                # Update central stats
                brand.product_count = counts.get("products", 0)
                central.add(brand)
                central.commit()
                success += 1

            except Exception as exc:
                logger.error("[%s] FAILED: %s", slug, exc, exc_info=True)
                failure += 1

        logger.info("Done. Success: %d, Failed: %d", success, failure)
        if failure > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
