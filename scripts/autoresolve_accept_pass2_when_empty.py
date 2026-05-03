"""Fourth-pass auto-resolve: when current product field is empty/null but
Pass 2 LLM extracted a value, accept Pass 2 — populates the product AND
resolves the review item. The LLM Pass 2 is grounded in the same HTML the
scraper saw, so it's reliable when the scraper missed a field.
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = "haira.db"

ACCEPTABLE_FIELDS = ["care_usage", "composition", "product_name", "description"]
FIELD_TO_COLUMN = {
    "care_usage": "care_usage",
    "composition": "composition",
    "product_name": "product_name",
    "description": "description",
}


def is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("BEGIN")

    placeholders = ",".join("?" * len(ACCEPTABLE_FIELDS))
    c.execute(
        f"SELECT rq.id, rq.product_id, rq.comparison_id, rq.field_name, "
        f"vc.pass_2_value FROM review_queue rq "
        f"JOIN validation_comparisons vc ON rq.comparison_id = vc.id "
        f"WHERE rq.status='pending' AND rq.field_name IN ({placeholders})",
        ACCEPTABLE_FIELDS,
    )
    items = c.fetchall()
    print(f"Pending text items in scope: {len(items)}")

    accepted = 0
    kept = 0
    now = datetime.now(timezone.utc).isoformat()

    for it in items:
        col = FIELD_TO_COLUMN[it["field_name"]]
        c.execute(f"SELECT {col} AS val FROM products WHERE id=?", (it["product_id"],))
        row = c.fetchone()
        if not row:
            kept += 1
            continue
        if not is_empty(row["val"]):
            kept += 1
            continue
        if is_empty(it["pass_2_value"]):
            kept += 1
            continue

        # Populate the product field with Pass 2 value
        c.execute(
            f"UPDATE products SET {col}=? WHERE id=?",
            (it["pass_2_value"], it["product_id"]),
        )
        c.execute(
            "UPDATE review_queue SET status='resolved', resolved_at=?, "
            "reviewer_notes='auto: accepted Pass 2 (current was empty)' WHERE id=?",
            (now, it["id"]),
        )
        c.execute(
            "UPDATE validation_comparisons SET resolution='accepted_pass_2', resolved_at=? WHERE id=?",
            (now, it["comparison_id"]),
        )
        accepted += 1

    print(f"Accepted Pass 2 (filled empty fields): {accepted}")
    print(f"Kept pending: {kept}")

    conn.commit()
    c.execute("SELECT status, COUNT(*) FROM review_queue GROUP BY status")
    print("\n=== Final review_queue ===")
    for r in c.fetchall():
        print(f"  {r[0]}: {r[1]}")
    conn.close()


if __name__ == "__main__":
    main()
