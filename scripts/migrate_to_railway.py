"""Migrate data from local SQLite to Railway PostgreSQL."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.storage.orm_models import (
    Base,
    ProductORM,
    ProductEvidenceORM,
    QuarantineDetailORM,
    BrandCoverageORM,
)


def migrate():
    sqlite_url = f"sqlite:///{Path(__file__).resolve().parents[1] / 'haira.db'}"
    pg_url = os.environ.get("RAILWAY_PG_URL")
    if not pg_url:
        print("ERROR: Set RAILWAY_PG_URL env var to the Railway Postgres public URL")
        print("Example: postgresql://postgres:xxx@crossover.proxy.rlwy.net:27385/railway")
        sys.exit(1)

    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    print(f"Source: {sqlite_url}")
    print(f"Target: {pg_url[:50]}...")

    src_engine = create_engine(sqlite_url)
    dst_engine = create_engine(pg_url)

    # Ensure tables exist on target
    Base.metadata.create_all(dst_engine)

    with Session(src_engine) as src_session, Session(dst_engine) as dst_session:
        # 1. Brand coverage
        brands = src_session.query(BrandCoverageORM).all()
        print(f"\nMigrating {len(brands)} brand coverage records...")
        for b in brands:
            dst_session.merge(_detach(b))
        dst_session.commit()
        print("  Done.")

        # 2. Products (batch)
        products = src_session.query(ProductORM).all()
        print(f"Migrating {len(products)} products...")
        batch_size = 200
        for i in range(0, len(products), batch_size):
            batch = products[i : i + batch_size]
            for p in batch:
                dst_session.merge(_detach(p))
            dst_session.commit()
            print(f"  {min(i + batch_size, len(products))}/{len(products)}")
        print("  Done.")

        # 3. Product evidence (batch)
        evidence = src_session.query(ProductEvidenceORM).all()
        print(f"Migrating {len(evidence)} evidence records...")
        for i in range(0, len(evidence), batch_size):
            batch = evidence[i : i + batch_size]
            for e in batch:
                dst_session.merge(_detach(e))
            dst_session.commit()
            print(f"  {min(i + batch_size, len(evidence))}/{len(evidence)}")
        print("  Done.")

        # 4. Quarantine details
        quarantine = src_session.query(QuarantineDetailORM).all()
        print(f"Migrating {len(quarantine)} quarantine records...")
        for q in quarantine:
            dst_session.merge(_detach(q))
        dst_session.commit()
        print("  Done.")

    print("\nMigration complete!")


def _detach(obj):
    """Create a detached copy of an ORM object for merging into another session."""
    from sqlalchemy import inspect as sa_inspect

    mapper = sa_inspect(type(obj))
    new = type(obj)()
    for col in mapper.columns:
        setattr(new, col.key, getattr(obj, col.key))
    return new


if __name__ == "__main__":
    migrate()
