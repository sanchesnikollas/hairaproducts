"""Dedupe review_queue: when multiple pending entries exist for the same
(product_id, field_name), keep only the newest and mark older as superseded.

This happens after multiple validate rounds — each run inserts new comparisons
and review_queue rows even when a stale pending row already exists for the
same field.

Usage:
  python scripts/autoresolve_dedupe_review.py
  python scripts/autoresolve_dedupe_review.py --dry-run
"""
from __future__ import annotations
import sqlite3
import sys

DB = "haira.db"


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        """
        SELECT product_id, field_name, GROUP_CONCAT(id, '|') ids,
               GROUP_CONCAT(created_at, '|') created
        FROM review_queue
        WHERE status='pending'
        GROUP BY product_id, field_name
        HAVING COUNT(*) > 1
        """
    )
    groups = c.fetchall()
    print(f"Groups with duplicates: {len(groups)}")

    total_to_supersede = 0
    for product_id, field, ids_concat, created_concat in groups:
        ids = ids_concat.split("|")
        created = created_concat.split("|")
        items = sorted(zip(ids, created), key=lambda x: x[1] or "", reverse=True)
        keep_id = items[0][0]
        supersede_ids = [it[0] for it in items[1:]]
        total_to_supersede += len(supersede_ids)
        if not dry_run and supersede_ids:
            placeholders = ",".join("?" for _ in supersede_ids)
            c.execute(
                f"UPDATE review_queue SET status='superseded', resolved_at=datetime('now'), reviewer_notes='Auto-deduped: superseded by newer entry for same field' WHERE id IN ({placeholders})",
                supersede_ids,
            )

    if not dry_run:
        conn.commit()

    print(f"{'Would supersede' if dry_run else 'Superseded'}: {total_to_supersede} duplicate review entries")

    c.execute("SELECT status, COUNT(*) FROM review_queue GROUP BY status")
    print("=== Final review_queue ===")
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]}")
    conn.close()


if __name__ == "__main__":
    main()
