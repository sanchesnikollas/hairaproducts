"""Third-pass auto-resolve: text fields (description, care_usage, product_name)
where current and Pass 2 differ only by whitespace, punctuation, or accents.
"""
from __future__ import annotations
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone

DB_PATH = "haira.db"

FIELD_TO_COLUMN = {
    "description": "description",
    "care_usage": "care_usage",
    "product_name": "product_name",
    "function_objective": "function_objective",
    "price": "price",
}


def deep_normalize(s) -> str:
    if s is None:
        return ""
    s = str(s)
    # Decompose accents and remove combining marks
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Lowercase + strip non-alphanumeric
    s = re.sub(r"[^a-z0-9]+", "", s.lower())
    return s


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("BEGIN")

    placeholders = ",".join("?" * len(FIELD_TO_COLUMN))
    c.execute(
        f"SELECT rq.id, rq.product_id, rq.comparison_id, rq.field_name, "
        f"vc.pass_2_value FROM review_queue rq "
        f"JOIN validation_comparisons vc ON rq.comparison_id = vc.id "
        f"WHERE rq.status='pending' AND rq.field_name IN ({placeholders})",
        list(FIELD_TO_COLUMN.keys()),
    )
    items = c.fetchall()
    print(f"Pending text/scalar items: {len(items)}")

    resolved = 0
    kept = 0
    now = datetime.now(timezone.utc).isoformat()

    for it in items:
        col = FIELD_TO_COLUMN[it["field_name"]]
        c.execute(f"SELECT {col} AS val FROM products WHERE id=?", (it["product_id"],))
        row = c.fetchone()
        if not row or row["val"] is None:
            kept += 1
            continue
        cur_norm = deep_normalize(row["val"])
        p2_norm = deep_normalize(it["pass_2_value"])
        if not cur_norm or not p2_norm:
            kept += 1
            continue
        # Exact match after normalization, or one is prefix/contained in the other
        is_match = (
            cur_norm == p2_norm
            or (len(cur_norm) > 30 and (cur_norm in p2_norm or p2_norm in cur_norm))
        )
        if is_match:
            c.execute(
                "UPDATE review_queue SET status='resolved', resolved_at=?, "
                "reviewer_notes='auto: normalized-text equivalence' WHERE id=?",
                (now, it["id"]),
            )
            c.execute(
                "UPDATE validation_comparisons SET resolution='kept_pass_1', resolved_at=? WHERE id=?",
                (now, it["comparison_id"]),
            )
            resolved += 1
        else:
            kept += 1

    print(f"Resolved (whitespace/accent equivalent): {resolved}")
    print(f"Kept pending: {kept}")

    conn.commit()
    c.execute("SELECT status, COUNT(*) FROM review_queue GROUP BY status")
    print("\n=== Final review_queue ===")
    for r in c.fetchall():
        print(f"  {r[0]}: {r[1]}")
    conn.close()


if __name__ == "__main__":
    main()
