#!/usr/bin/env python3
"""Migrate data from local SQLite to production PostgreSQL (single-DB mode).

Usage:
    DATABASE_URL=postgresql://... python3 scripts/migrate_single_db.py
    railway run python3 scripts/migrate_single_db.py
"""
from __future__ import annotations

import logging
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, make_transient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

BATCH_SIZE = 200
SOURCE_DB = "sqlite:///haira.db"


def _normalise_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _bulk_insert(dest_engine, rows, label):
    if not rows:
        logger.info("  %s: 0 rows (skip)", label)
        return 0
    with Session(dest_engine) as dest:
        for i in range(0, len(rows), BATCH_SIZE):
            dest.add_all(rows[i : i + BATCH_SIZE])
            dest.flush()
        dest.commit()
    logger.info("  %s: %d rows", label, len(rows))
    return len(rows)


def _expunge_all(session, rows):
    for r in rows:
        session.expunge(r)
        make_transient(r)
    return rows


def main():
    dest_url = os.environ.get("DATABASE_URL", "")
    if not dest_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)
    dest_url = _normalise_url(dest_url)

    source_engine = create_engine(SOURCE_DB)
    dest_engine = create_engine(dest_url, pool_pre_ping=True)

    from src.storage.orm_models import (
        Base, ProductORM, ProductEvidenceORM, QuarantineDetailORM,
        BrandCoverageORM, IngredientORM, IngredientAliasORM,
        ProductIngredientORM, ClaimORM, ClaimAliasORM, ProductClaimORM,
        ProductImageORM, ProductCompositionORM, ValidationComparisonORM,
        ReviewQueueORM,
    )

    # Ensure tables exist
    Base.metadata.create_all(dest_engine)

    # Check what brands already exist in dest
    with Session(dest_engine) as dest:
        existing_brands = {r[0] for r in dest.execute(text("SELECT DISTINCT brand_slug FROM products")).fetchall()}
    logger.info("Existing brands in dest: %s", existing_brands or "(none)")

    with Session(source_engine) as src:
        # Get brands to migrate
        all_brands = [r[0] for r in src.execute(text("SELECT DISTINCT brand_slug FROM products")).fetchall()]
        brands_to_migrate = [b for b in all_brands if b not in existing_brands]

        if not brands_to_migrate:
            logger.info("All brands already migrated!")
            return

        logger.info("Brands to migrate: %s", brands_to_migrate)

        # Collect all ingredient IDs we'll need
        all_product_ids = []

        for brand_slug in brands_to_migrate:
            logger.info("=== %s ===", brand_slug)

            # Products
            products = src.query(ProductORM).filter(ProductORM.brand_slug == brand_slug).all()
            product_ids = [p.id for p in products]
            all_product_ids.extend(product_ids)
            _expunge_all(src, products)
            _bulk_insert(dest_engine, products, "products")

            if not product_ids:
                continue

            # Evidence
            evidence = []
            for i in range(0, len(product_ids), 500):
                chunk = product_ids[i : i + 500]
                evidence.extend(src.query(ProductEvidenceORM).filter(ProductEvidenceORM.product_id.in_(chunk)).all())
            _expunge_all(src, evidence)
            _bulk_insert(dest_engine, evidence, "evidence")

            # Quarantine
            qd = []
            for i in range(0, len(product_ids), 500):
                chunk = product_ids[i : i + 500]
                qd.extend(src.query(QuarantineDetailORM).filter(QuarantineDetailORM.product_id.in_(chunk)).all())
            _expunge_all(src, qd)
            _bulk_insert(dest_engine, qd, "quarantine")

            # Product ingredients
            pi_rows = []
            for i in range(0, len(product_ids), 500):
                chunk = product_ids[i : i + 500]
                pi_rows.extend(src.query(ProductIngredientORM).filter(ProductIngredientORM.product_id.in_(chunk)).all())
            _expunge_all(src, pi_rows)

            # Get required ingredient IDs
            ingredient_ids = list({pi.ingredient_id for pi in pi_rows})

            # Check which ingredients already exist in dest
            if ingredient_ids:
                with Session(dest_engine) as dest:
                    existing_ing = {r[0] for r in dest.execute(text("SELECT id FROM ingredients")).fetchall()}
                new_ing_ids = [iid for iid in ingredient_ids if iid not in existing_ing]

                if new_ing_ids:
                    ingredients = []
                    aliases = []
                    for i in range(0, len(new_ing_ids), 500):
                        chunk = new_ing_ids[i : i + 500]
                        ingredients.extend(src.query(IngredientORM).filter(IngredientORM.id.in_(chunk)).all())
                        aliases.extend(src.query(IngredientAliasORM).filter(IngredientAliasORM.ingredient_id.in_(chunk)).all())
                    _expunge_all(src, ingredients)
                    _expunge_all(src, aliases)
                    _bulk_insert(dest_engine, ingredients, "ingredients")
                    _bulk_insert(dest_engine, aliases, "ingredient_aliases")

            _bulk_insert(dest_engine, pi_rows, "product_ingredients")

            # Claims
            pc_rows = []
            for i in range(0, len(product_ids), 500):
                chunk = product_ids[i : i + 500]
                pc_rows.extend(src.query(ProductClaimORM).filter(ProductClaimORM.product_id.in_(chunk)).all())
            _expunge_all(src, pc_rows)

            if pc_rows:
                claim_ids = list({pc.claim_id for pc in pc_rows})
                with Session(dest_engine) as dest:
                    existing_claims = {r[0] for r in dest.execute(text("SELECT id FROM claims")).fetchall()}
                new_claim_ids = [cid for cid in claim_ids if cid not in existing_claims]

                if new_claim_ids:
                    claims = []
                    claim_aliases = []
                    for i in range(0, len(new_claim_ids), 500):
                        chunk = new_claim_ids[i : i + 500]
                        claims.extend(src.query(ClaimORM).filter(ClaimORM.id.in_(chunk)).all())
                        claim_aliases.extend(src.query(ClaimAliasORM).filter(ClaimAliasORM.claim_id.in_(chunk)).all())
                    _expunge_all(src, claims)
                    _expunge_all(src, claim_aliases)
                    _bulk_insert(dest_engine, claims, "claims")
                    _bulk_insert(dest_engine, claim_aliases, "claim_aliases")

            _bulk_insert(dest_engine, pc_rows, "product_claims")

            # Images
            images = []
            for i in range(0, len(product_ids), 500):
                chunk = product_ids[i : i + 500]
                images.extend(src.query(ProductImageORM).filter(ProductImageORM.product_id.in_(chunk)).all())
            _expunge_all(src, images)
            _bulk_insert(dest_engine, images, "images")

            # Compositions
            comps = []
            for i in range(0, len(product_ids), 500):
                chunk = product_ids[i : i + 500]
                comps.extend(src.query(ProductCompositionORM).filter(ProductCompositionORM.product_id.in_(chunk)).all())
            _expunge_all(src, comps)
            _bulk_insert(dest_engine, comps, "compositions")

        # Coverage (all brands at once)
        coverage = src.query(BrandCoverageORM).filter(BrandCoverageORM.brand_slug.in_(brands_to_migrate)).all()
        _expunge_all(src, coverage)
        _bulk_insert(dest_engine, coverage, "brand_coverage")

    logger.info("Migration complete!")

    # Verify
    with Session(dest_engine) as dest:
        total = dest.execute(text("SELECT COUNT(*) FROM products")).scalar()
        brands = dest.execute(text("SELECT brand_slug, COUNT(*) FROM products GROUP BY brand_slug ORDER BY COUNT(*) DESC")).fetchall()
        logger.info("Verification - Total products: %d", total)
        for brand, count in brands:
            logger.info("  %s: %d", brand, count)

    dest_engine.dispose()


if __name__ == "__main__":
    main()
