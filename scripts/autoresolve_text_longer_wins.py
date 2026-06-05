"""Layer 5: For text fields, when Pass 1 (current) is much longer than Pass 2,
keep Pass 1. This handles the common case where Pass 2 LLM generates a concise
summary while the scraper captured the full marketing copy from the site.

Heuristic:
  - Field in {description, care_usage, composition}
  - Pass 2 not empty AND Pass 1 length > 2 * Pass 2 length AND Pass 1 > 200 chars
  - OR Pass 2 empty AND Pass 1 > 50 chars

Usage:
  python scripts/autoresolve_text_longer_wins.py
  python scripts/autoresolve_text_longer_wins.py --dry-run
"""
from __future__ import annotations
import sqlite3
import sys

DB = "haira.db"
FIELDS = ("description", "care_usage", "composition")


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    placeholders = ",".join("?" for _ in FIELDS)
    c.execute(
        f"""
        SELECT rq.id, rq.field_name, vc.pass_1_value, vc.pass_2_value
        FROM review_queue rq
        JOIN validation_comparisons vc ON rq.comparison_id = vc.id
        WHERE rq.status='pending' AND rq.field_name IN ({placeholders})
        """,
        FIELDS,
    )
    candidates = c.fetchall()
    print(f"Pending text items in scope: {len(candidates)}")

    resolved = 0
    for rid, field, p1, p2 in candidates:
        p1 = p1 or ""
        p2 = p2 or ""
        keep_p1 = False
        if not p2 and len(p1) > 50:
            keep_p1 = True
        elif p2 and len(p1) > 2 * len(p2) and len(p1) > 200:
            keep_p1 = True

        if keep_p1:
            resolved += 1
            if not dry_run:
                c.execute(
                    "UPDATE review_queue SET status='resolved', resolved_at=datetime('now'), reviewer_notes='Auto-resolved: Pass 1 (current) is more complete than Pass 2 (LLM summary)' WHERE id=?",
                    (rid,),
                )

    if not dry_run:
        conn.commit()

    print(f"{'Would resolve' if dry_run else 'Resolved'}: {resolved}")
    print(f"Kept pending: {len(candidates) - resolved}")

    c.execute("SELECT status, COUNT(*) FROM review_queue GROUP BY status")
    print("=== Final review_queue ===")
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]}")
    conn.close()


if __name__ == "__main__":
    main()
