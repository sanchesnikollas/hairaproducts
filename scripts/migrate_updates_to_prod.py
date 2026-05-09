"""Push UPDATE-only changes (product_labels, product_category) to production.

Use after migrate_to_railway_api.py — that script is INSERT-only.
This pushes updates for fields like product_labels that may have changed
on existing rows (e.g., after running labels/classify CLI on local).

Usage:
  MIGRATION_SECRET=... RAILWAY_URL=... python scripts/migrate_updates_to_prod.py

Pushes only fields that meaningfully changed (non-null in local).
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
BATCH_SIZE = 100  # rows per API call

UPDATE_FIELDS = ["product_labels", "product_category", "care_usage", "composition", "description", "size_volume"]


def main():
    if not SECRET:
        print("ERROR: Set MIGRATION_SECRET env var")
        sys.exit(1)

    conn = sqlite3.connect("haira.db")
    conn.row_factory = sqlite3.Row

    cols = ", ".join(["id"] + UPDATE_FIELDS)
    rows = list(conn.execute(
        f"SELECT {cols} FROM products WHERE product_labels IS NOT NULL OR product_category IS NOT NULL"
    ))
    print(f"Total rows with updates to push: {len(rows)}")

    client = httpx.Client(timeout=60)
    total_updated = 0

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        updates = []
        for r in batch:
            d = {"id": r["id"]}
            for f in UPDATE_FIELDS:
                v = r[f]
                if v is None:
                    continue
                # Parse JSON columns to objects
                if f in ("product_labels",) and isinstance(v, str):
                    try:
                        v = json.loads(v)
                    except (json.JSONDecodeError, ValueError):
                        pass
                d[f] = v
            updates.append(d)

        try:
            resp = client.post(
                f"{BASE_URL}/api/admin/migrate-update",
                json={"secret": SECRET, "updates": updates},
            )
            data = resp.json()
            updated = data.get("updated", 0)
            total_updated += updated
            errors = data.get("errors", [])
            if errors:
                print(f"  batch {i//BATCH_SIZE+1}: {updated} updated, errors: {errors[:1]}")
            else:
                print(f"  batch {i//BATCH_SIZE+1}: {updated} updated", flush=True)
        except Exception as e:
            print(f"  batch {i//BATCH_SIZE+1}: ERROR - {e}", flush=True)
        time.sleep(0.3)

    print(f"\n=== TOTAL UPDATED: {total_updated} ===")
    conn.close()
    client.close()


if __name__ == "__main__":
    main()
