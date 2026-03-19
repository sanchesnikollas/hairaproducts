"""Migrate remaining evidence + quarantine from local SQLite to Railway PostgreSQL."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.storage.orm_models import Base, ProductEvidenceORM, QuarantineDetailORM


def migrate():
    sqlite_url = f"sqlite:///{Path(__file__).resolve().parents[1] / 'haira.db'}"
    pg_url = os.environ["RAILWAY_PG_URL"]
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    src_engine = create_engine(sqlite_url)
    dst_engine = create_engine(pg_url)

    with Session(src_engine) as src_session, Session(dst_engine) as dst_session:
        # Get already-migrated evidence IDs
        existing_ids = {r[0] for r in dst_session.execute(text("SELECT id FROM product_evidence")).fetchall()}
        print(f"Already migrated: {len(existing_ids)} evidence records")

        # Migrate remaining evidence
        all_evidence = src_session.query(ProductEvidenceORM).all()
        remaining = [e for e in all_evidence if e.id not in existing_ids]
        print(f"Remaining evidence to migrate: {len(remaining)}")

        batch_size = 200
        for i in range(0, len(remaining), batch_size):
            batch = remaining[i : i + batch_size]
            for e in batch:
                new = ProductEvidenceORM()
                for col in ProductEvidenceORM.__table__.columns:
                    setattr(new, col.key, getattr(e, col.key))
                dst_session.merge(new)
            dst_session.commit()
            print(f"  Evidence: {min(i + batch_size, len(remaining))}/{len(remaining)}")
        print("  Evidence done.")

        # Migrate quarantine
        quarantine = src_session.query(QuarantineDetailORM).all()
        print(f"Migrating {len(quarantine)} quarantine records...")
        for q in quarantine:
            new = QuarantineDetailORM()
            for col in QuarantineDetailORM.__table__.columns:
                setattr(new, col.key, getattr(q, col.key))
            dst_session.merge(new)
        dst_session.commit()
        print("  Quarantine done.")

    print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
