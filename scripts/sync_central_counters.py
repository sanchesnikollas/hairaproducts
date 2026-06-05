#!/usr/bin/env python3
"""Sync denormalised brand counters from the live product table.

Two modes, picked automatically by env vars:

* Multi-DB (`CENTRAL_DATABASE_URL` set): updates `BrandDatabaseORM` in central.
* Single-DB (only `DATABASE_URL`): updates `BrandCoverageORM` in the same DB.

Usage:
    DATABASE_URL=postgresql://... python scripts/sync_central_counters.py
    DATABASE_URL=postgresql://... python scripts/sync_central_counters.py --brand davines

Prints a summary table and exits non-zero if any brand failed.
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.central_sync import (
    sync_all_brands,
    sync_all_coverage,
    sync_brand_counters,
    sync_brand_coverage,
)
from src.storage.db_router import DatabaseRouter


def _normalise_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync brand counters.")
    parser.add_argument("--brand", help="Sync a single brand slug (default: all).")
    args = parser.parse_args()

    central_url = os.environ.get("CENTRAL_DATABASE_URL", "").strip()
    if central_url:
        engine = create_engine(_normalise_url(central_url), pool_pre_ping=True)
        router = DatabaseRouter(engine)
        if args.brand:
            results = [sync_brand_counters(router, args.brand)]
        else:
            results = sync_all_brands(router)
        mode = "multi-db"
    else:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            print("ERROR: DATABASE_URL not set", file=sys.stderr)
            return 2
        engine = create_engine(_normalise_url(url), pool_pre_ping=True)
        with Session(engine) as session:
            if args.brand:
                results = [sync_brand_coverage(session, args.brand)]
            else:
                results = sync_all_coverage(session)
        mode = "single-db"

    print(f"mode: {mode}\n")
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
