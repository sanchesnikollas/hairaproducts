"""One-time migration: imports baked JSON data into PostgreSQL.

Runs at container startup. Skips if data already exists (idempotent via ON CONFLICT DO NOTHING).
Delete migration_data.json after successful migration.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

DATA_FILE = Path(__file__).parent / "migration_data.json"

TABLE_ORDER = [
    "ingredients", "ingredient_aliases",
    "products", "product_evidence", "quarantine_details",
    "product_ingredients", "product_claims", "product_images",
    "product_compositions", "brand_coverage",
]

BOOL_COLUMNS = {"is_kit", "is_active", "manually_verified", "manually_overridden"}


def migrate():
    if not DATA_FILE.exists():
        print("No migration_data.json found, skipping baked migration.")
        return

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("No DATABASE_URL set, skipping migration.")
        return

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(db_url)

    with open(DATA_FILE) as f:
        data = json.load(f)

    total_inserted = 0
    total_skipped = 0

    for table in TABLE_ORDER:
        rows = data.get(table, [])
        if not rows:
            continue

        # Prepare params
        prepared = []
        for row in rows:
            params = {}
            for k, v in row.items():
                if isinstance(v, (dict, list)):
                    params[k] = json.dumps(v, ensure_ascii=False)
                elif k in BOOL_COLUMNS and isinstance(v, int):
                    params[k] = bool(v)
                else:
                    params[k] = v
            prepared.append(params)

        cols = list(prepared[0].keys())
        col_names = ", ".join(cols)
        placeholders = ", ".join(f":{c}" for c in cols)
        sql = text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING")

        inserted = 0
        skipped = 0
        try:
            with engine.begin() as conn:
                for params in prepared:
                    result = conn.execute(sql, params)
                    if result.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
        except Exception as e:
            print(f"  ERROR on {table}: {e}")
            continue

        print(f"  {table}: {inserted} inserted, {skipped} skipped")
        total_inserted += inserted
        total_skipped += skipped

    print(f"Migration complete: {total_inserted} inserted, {total_skipped} skipped")


if __name__ == "__main__":
    migrate()
