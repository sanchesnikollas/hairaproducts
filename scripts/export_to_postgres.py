"""
Export local SQLite data to a PostgreSQL database.

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/db python scripts/export_to_postgres.py

This reads from the local haira.db and writes all products + evidence
to the target PostgreSQL database.
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.orm_models import Base, ProductORM, ProductEvidenceORM, QuarantineDetailORM, BrandCoverageORM


def main():
    target_url = os.environ.get("DATABASE_URL")
    if not target_url:
        print("Set DATABASE_URL to the target PostgreSQL URL")
        sys.exit(1)

    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql://", 1)

    # Source: local SQLite
    source = create_engine("sqlite:///haira.db")
    # Target: PostgreSQL
    target = create_engine(target_url)

    # Create tables on target
    Base.metadata.create_all(target)

    with Session(source) as src, Session(target) as dst:
        # Products
        products = src.query(ProductORM).all()
        print(f"Exporting {len(products)} products...")
        for p in products:
            data = {c.name: getattr(p, c.name) for c in ProductORM.__table__.columns}
            dst.merge(ProductORM(**data))
        dst.flush()

        # Evidence
        evidence = src.query(ProductEvidenceORM).all()
        print(f"Exporting {len(evidence)} evidence records...")
        for e in evidence:
            data = {c.name: getattr(e, c.name) for c in ProductEvidenceORM.__table__.columns}
            dst.merge(ProductEvidenceORM(**data))
        dst.flush()

        # Quarantine
        quarantine = src.query(QuarantineDetailORM).all()
        print(f"Exporting {len(quarantine)} quarantine records...")
        for q in quarantine:
            data = {c.name: getattr(q, c.name) for c in QuarantineDetailORM.__table__.columns}
            dst.merge(QuarantineDetailORM(**data))
        dst.flush()

        # Brand coverage
        coverages = src.query(BrandCoverageORM).all()
        print(f"Exporting {len(coverages)} brand coverage records...")
        for c_item in coverages:
            data = {c.name: getattr(c_item, c.name) for c in BrandCoverageORM.__table__.columns}
            dst.merge(BrandCoverageORM(**data))

        dst.commit()
        print("Done!")


if __name__ == "__main__":
    main()
