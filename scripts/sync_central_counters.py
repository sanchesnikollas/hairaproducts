#!/usr/bin/env python3
"""Sync product_count + inci_rate on the central brand registry from each brand DB.

Usage:
    CENTRAL_DATABASE_URL=postgresql://... python scripts/sync_central_counters.py
    CENTRAL_DATABASE_URL=postgresql://... python scripts/sync_central_counters.py --brand davines

Reads `CENTRAL_DATABASE_URL` (and per-brand URLs stored in `brand_databases`).
Prints a summary table and exits non-zero if any brand failed.
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine

from src.storage.central_sync import sync_all_brands, sync_brand_counters
from src.storage.db_router import DatabaseRouter


def _normalise_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync central brand counters.")
    parser.add_argument("--brand", help="Sync a single brand slug (default: all).")
    args = parser.parse_args()

    url = os.environ.get("CENTRAL_DATABASE_URL")
    if not url:
        print("ERROR: CENTRAL_DATABASE_URL not set", file=sys.stderr)
        return 2

    engine = create_engine(_normalise_url(url), pool_pre_ping=True)
    router = DatabaseRouter(engine)

    if args.brand:
        results = [sync_brand_counters(router, args.brand)]
    else:
        results = sync_all_brands(router)

    print(f"{'brand':<35} {'old_count':>10} {'new_count':>10} {'old_rate':>9} {'new_rate':>9}  status")
    print("-" * 95)
    changed = 0
    failed = 0
    for r in results:
        status = "ok"
        if r.error:
            status = f"ERR: {r.error[:30]}"
            failed += 1
        elif r.changed:
            status = "updated"
            changed += 1
        print(
            f"{r.brand_slug:<35} {r.previous_count:>10} {r.new_count:>10} "
            f"{r.previous_rate*100:>8.2f}% {r.new_rate*100:>8.2f}%  {status}"
        )

    print("-" * 95)
    print(f"total: {len(results)}  updated: {changed}  failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
