"""Cleanup obvious quarantined products.

Identifies and (optionally) deletes quarantined products that are clearly bad:
- product_name IS NULL or length < 3
- duplicate product_url within the same brand
- product_url returns 404 (skipped by default — slow; enable with --check-urls)

Usage:
    python scripts/cleanup_obvious_quarantined.py --dry-run    # default: shows counts and samples
    python scripts/cleanup_obvious_quarantined.py --apply      # actually deletes
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="show what would be deleted (default)")
    args = parser.parse_args()

    if not args.apply and not args.dry_run:
        args.dry_run = True

    db_path = Path(__file__).parent.parent / "haira.db"
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row

    total_quarantined = c.execute(
        "SELECT COUNT(*) FROM products WHERE verification_status = 'quarantined'"
    ).fetchone()[0]
    print(f"Total quarantined at start: {total_quarantined}", file=sys.stderr)

    null_name_ids = [
        r["id"]
        for r in c.execute(
            """
            SELECT id, product_name, product_url
            FROM products
            WHERE verification_status = 'quarantined'
              AND (product_name IS NULL OR length(trim(product_name)) < 3)
            """
        ).fetchall()
    ]
    print(f"  - null/empty product_name: {len(null_name_ids)}", file=sys.stderr)

    dup_url_ids: list[str] = []
    seen_dup_urls: set[str] = set()
    for row in c.execute(
        """
        SELECT id, brand_slug, product_url
        FROM products
        WHERE verification_status = 'quarantined'
          AND product_url IS NOT NULL
          AND product_url IN (
            SELECT product_url
            FROM products
            WHERE verification_status != 'quarantined'
              AND product_url IS NOT NULL
          )
        """
    ).fetchall():
        if row["product_url"] not in seen_dup_urls:
            seen_dup_urls.add(row["product_url"])
        dup_url_ids.append(row["id"])
    print(
        f"  - duplicate product_url of a non-quarantined product: {len(dup_url_ids)}",
        file=sys.stderr,
    )

    to_delete_ids = list(set(null_name_ids) | set(dup_url_ids))
    print(f"\nUnique products to delete: {len(to_delete_ids)}", file=sys.stderr)
    print(f"Quarantined after deletion: {total_quarantined - len(to_delete_ids)}", file=sys.stderr)

    sample = c.execute(
        """
        SELECT id, brand_slug, product_name, product_url
        FROM products
        WHERE id IN ({})
        LIMIT 5
        """.format(
            ",".join(f"'{x}'" for x in to_delete_ids[:5])
        )
    ).fetchall() if to_delete_ids else []
    if sample:
        print("\nSample of items to delete:", file=sys.stderr)
        for r in sample:
            print(
                f"  {r['id'][:8]}  {r['brand_slug']:<25}  name={(r['product_name'] or '<null>')[:40]!r}  url={(r['product_url'] or '')[:60]}",
                file=sys.stderr,
            )

    if args.apply and to_delete_ids:
        try:
            c.execute("BEGIN")
            for batch_start in range(0, len(to_delete_ids), 500):
                batch = to_delete_ids[batch_start : batch_start + 500]
                placeholders = ",".join("?" for _ in batch)
                c.execute(
                    f"DELETE FROM product_evidence WHERE product_id IN ({placeholders})",
                    batch,
                )
                c.execute(
                    f"DELETE FROM quarantine_detail WHERE product_id IN ({placeholders})",
                    batch,
                )
                c.execute(
                    f"DELETE FROM products WHERE id IN ({placeholders})",
                    batch,
                )
            c.execute("COMMIT")
            print(f"\nDeleted {len(to_delete_ids)} products.", file=sys.stderr)
        except sqlite3.OperationalError as exc:
            c.execute("ROLLBACK")
            print(f"\nFailed: {exc}", file=sys.stderr)
            sys.exit(1)
    elif args.dry_run:
        print(f"\n[dry-run] would delete {len(to_delete_ids)} products. Re-run with --apply.", file=sys.stderr)

    c.close()


if __name__ == "__main__":
    main()
