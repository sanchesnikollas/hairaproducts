#!/usr/bin/env python3
"""Send JSON migration data to production via admin/migrate-json endpoint.

Usage:
    python3 scripts/export_json_migration.py > /tmp/migration.json
    python3 scripts/send_migration.py --url https://haira-app-production-deb8.up.railway.app --secret <secret>
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error

BATCH_SIZE = 200  # rows per request

TABLE_ORDER = [
    "ingredients",
    "ingredient_aliases",
    "claims",
    "claim_aliases",
    "products",
    "product_evidence",
    "quarantine_details",
    "product_ingredients",
    "product_claims",
    "product_images",
    "product_compositions",
    "brand_coverage",
]


def send_batch(url: str, secret: str, table: str, rows: list[dict]) -> dict:
    payload = json.dumps({"secret": secret, "table": table, "rows": rows}, ensure_ascii=False, default=str).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/api/admin/migrate-json",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"error": f"HTTP {e.code}: {body[:500]}"}
    except Exception as e:
        return {"error": str(e)}


def check_status(url: str, secret: str) -> dict:
    req = urllib.request.Request(f"{url}/api/admin/migrate-status?secret={secret}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Production app URL")
    parser.add_argument("--secret", required=True, help="Migration secret")
    parser.add_argument("--json-file", default="/tmp/migration.json", help="JSON data file")
    parser.add_argument("--status-only", action="store_true", help="Just check current status")
    parser.add_argument("--skip-tables", nargs="*", default=[], help="Tables to skip")
    args = parser.parse_args()

    if args.status_only:
        status = check_status(args.url, args.secret)
        print(json.dumps(status, indent=2))
        return

    with open(args.json_file) as f:
        data = json.load(f)

    for table in TABLE_ORDER:
        if table in args.skip_tables:
            print(f"  {table}: SKIPPED by user")
            continue
        rows = data.get(table, [])
        if not rows:
            print(f"  {table}: 0 rows (skip)")
            continue

        total_inserted = 0
        total_skipped = 0

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE

            result = send_batch(args.url, args.secret, table, batch)

            if "error" in result:
                print(f"  {table} batch {batch_num}/{total_batches}: FAILED - {result['error']}")
                sys.exit(1)

            total_inserted += result.get("inserted", 0)
            total_skipped += result.get("skipped", 0)

            if total_batches > 1:
                print(f"  {table} batch {batch_num}/{total_batches}: +{result.get('inserted', 0)} inserted, {result.get('skipped', 0)} skipped")

        print(f"  {table}: {total_inserted} inserted, {total_skipped} skipped (of {len(rows)} total)")

    print("\nChecking final status...")
    status = check_status(args.url, args.secret)
    print(f"\nBrands in production: {status.get('brands', {})}")
    print(f"Total products: {status.get('products', '?')}")


if __name__ == "__main__":
    main()
