"""Migrate products from local JSON export to production PostgreSQL.

Usage:
    python scripts/migrate_products_to_prod.py scripts/migration_eudora_boticario.json

Requires DATABASE_URL env var pointing to production PostgreSQL.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.orm_models import Base, ProductORM, BrandCoverageORM


def parse_datetime(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


def migrate(json_path: str, db_url: str):
    engine = create_engine(db_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)

    with open(json_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    print(f"Loaded {len(products)} products from {json_path}")

    datetime_cols = {"extracted_at", "created_at", "updated_at"}
    json_cols = {
        "image_urls_gallery", "inci_ingredients", "benefits_claims",
        "variants", "product_labels", "confidence_factors",
        "interpretation_data", "application_data", "decision_data",
    }

    inserted = 0
    updated = 0
    skipped = 0

    with Session(engine) as session:
        for row in products:
            product_id = row["id"]
            existing = session.query(ProductORM).filter(ProductORM.id == product_id).first()

            if existing:
                if existing.verification_status == "verified_inci":
                    skipped += 1
                    continue
                # Update existing product
                for key, val in row.items():
                    if key in ("id", "created_at"):
                        continue
                    if key in datetime_cols:
                        val = parse_datetime(val)
                    setattr(existing, key, val)
                updated += 1
            else:
                for key in datetime_cols:
                    row[key] = parse_datetime(row.get(key))
                product = ProductORM(**row)
                session.add(product)
                inserted += 1

            if (inserted + updated) % 100 == 0:
                session.commit()
                print(f"  Progress: {inserted} inserted, {updated} updated, {skipped} skipped")

        session.commit()

        # Update coverage for affected brands
        brand_slugs = list({r["brand_slug"] for r in products})
        for slug in brand_slugs:
            total = session.query(ProductORM).filter(ProductORM.brand_slug == slug).count()
            verified = session.query(ProductORM).filter(
                ProductORM.brand_slug == slug,
                ProductORM.verification_status == "verified_inci",
            ).count()
            catalog = session.query(ProductORM).filter(
                ProductORM.brand_slug == slug,
                ProductORM.verification_status == "catalog_only",
            ).count()

            coverage = session.query(BrandCoverageORM).filter(
                BrandCoverageORM.brand_slug == slug
            ).first()
            if coverage:
                coverage.total_products = total
                coverage.verified_inci_count = verified
                coverage.catalog_only_count = catalog
                coverage.updated_at = datetime.now(timezone.utc)
            else:
                coverage = BrandCoverageORM(
                    brand_slug=slug,
                    total_products=total,
                    verified_inci_count=verified,
                    catalog_only_count=catalog,
                    status="done",
                )
                session.add(coverage)

            print(f"  Coverage {slug}: {total} total, {verified} verified, {catalog} catalog")

        session.commit()

    print(f"\nDone: {inserted} inserted, {updated} updated, {skipped} skipped")


if __name__ == "__main__":
    import os

    if len(sys.argv) < 2:
        print("Usage: python scripts/migrate_products_to_prod.py <json_file>")
        sys.exit(1)

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL env var required (production PostgreSQL)")
        sys.exit(1)

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    migrate(sys.argv[1], db_url)
