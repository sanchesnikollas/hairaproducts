"""Migrate data from local SQLite to Railway PostgreSQL via admin API.

Usage: python scripts/migrate_to_railway_api.py

Requires MIGRATION_SECRET env var to match the one set on Railway.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

import httpx

BASE_URL = os.environ.get("RAILWAY_URL", "https://haira-app-production-deb8.up.railway.app")
SECRET = os.environ.get("MIGRATION_SECRET", "")
BATCH_SIZE = 200  # rows per API call

# Migrate ALL data — no brand filter
TABLES = [
    ("ingredients", "SELECT * FROM ingredients"),
    ("ingredient_aliases", "SELECT * FROM ingredient_aliases"),
    ("claims", "SELECT * FROM claims"),
    ("claim_aliases", "SELECT * FROM claim_aliases"),
    ("products", "SELECT * FROM products"),
    ("product_evidence", "SELECT * FROM product_evidence"),
    ("quarantine_details", "SELECT * FROM quarantine_details"),
    ("product_ingredients", "SELECT * FROM product_ingredients"),
    ("product_claims", "SELECT * FROM product_claims"),
    ("product_images", "SELECT * FROM product_images"),
    ("product_compositions", "SELECT * FROM product_compositions"),
    ("brand_coverage", "SELECT * FROM brand_coverage"),
]


def convert_row(row: dict) -> dict:
    """Convert SQLite row values for JSON serialization."""
    result = {}
    for k, v in row.items():
        if isinstance(v, bytes):
            result[k] = v.decode("utf-8", errors="replace")
        elif isinstance(v, str) and v.startswith(("[", "{")):
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, ValueError):
                result[k] = v
        else:
            result[k] = v
    return result


def migrate():
    if not SECRET:
        print("ERROR: Set MIGRATION_SECRET env var")
        sys.exit(1)

    conn = sqlite3.connect("haira.db")
    conn.row_factory = sqlite3.Row
    client = httpx.Client(timeout=120)

    for table, query in TABLES:
        rows = conn.execute(query).fetchall()

        rows = [convert_row(dict(r)) for r in rows]
        print(f"\n{table}: {len(rows)} rows to migrate")

        if not rows:
            continue

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            try:
                resp = client.post(
                    f"{BASE_URL}/api/admin/migrate-json",
                    json={"secret": SECRET, "table": table, "rows": batch},
                )
                data = resp.json()
                print(f"  batch {i//BATCH_SIZE+1}: {data.get('inserted',0)} inserted, {data.get('skipped',0)} skipped, errors: {data.get('errors',[])}")
                if data.get("errors"):
                    print(f"    ERRORS: {data['errors'][:2]}")
            except Exception as e:
                print(f"  batch {i//BATCH_SIZE+1}: ERROR - {e}")
            time.sleep(0.5)

    # Check status
    try:
        resp = client.get(f"{BASE_URL}/api/admin/migrate-status?secret={SECRET}")
        status = resp.json()
        print(f"\n=== Migration Status ===")
        for table, count in status.items():
            if table != "brands":
                print(f"  {table}: {count}")
        if "brands" in status:
            print(f"\nBrands:")
            for brand, count in sorted(status["brands"].items(), key=lambda x: -x[1])[:20]:
                print(f"  {brand}: {count}")
    except Exception as e:
        print(f"Status check failed: {e}")

    conn.close()
    client.close()


if __name__ == "__main__":
    migrate()
