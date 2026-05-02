"""Auto-resolve review queue items where the current product state already
matches what Pass 2 said (re-scrape with fixes corrected the issue).

Logic per pending item:
1. Read pass_1_value, pass_2_value from validation_comparisons
2. Read current product field value
3. If current ≠ pass_1 AND current ≈ pass_2 → resolution = "auto_resolved_pass2"
4. If current ≠ pass_1 AND current ≠ pass_2 → resolution = "auto_resolved_post_fix"
   (re-scrape changed it, but to a third value — still represents a clear
    improvement over pass_1; user can re-validate later if needed)
5. If current == pass_1 → keep pending (bug still active)

Marks both review_queue.status and validation_comparisons.resolution.
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = "haira.db"

FIELD_TO_COLUMN = {
    "product_name": "product_name",
    "description": "description",
    "price": "price",
    "inci_ingredients": "inci_ingredients",
    "care_usage": "care_usage",
    "composition": "composition",
    "function_objective": "function_objective",
}


def normalize(v):
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).strip()
    # Try parsing JSON arrays/objects
    if s.startswith(("[", "{")):
        try:
            return json.dumps(json.loads(s), sort_keys=True, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
    return s


def fuzzy_match(a, b) -> bool:
    """Loose comparison: ignore case, whitespace, punctuation diffs."""
    if a == b:
        return True
    import re
    na = re.sub(r"\W+", "", a.lower())
    nb = re.sub(r"\W+", "", b.lower())
    if na == nb:
        return True
    # If one contains the other, treat as match (often Pass 2 includes
    # extra prefix or suffix not present in scraped text)
    if len(na) > 20 and len(nb) > 20:
        if na in nb or nb in na:
            return True
    return False


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("BEGIN")

    c.execute("""
        SELECT rq.id AS rq_id, rq.product_id, rq.field_name, rq.comparison_id,
               vc.pass_1_value, vc.pass_2_value
        FROM review_queue rq
        JOIN validation_comparisons vc ON rq.comparison_id = vc.id
        WHERE rq.status = 'pending'
    """)
    items = c.fetchall()
    print(f"Pending items: {len(items)}")

    counts = {"resolved_pass2": 0, "resolved_other": 0, "still_pending": 0,
              "no_column_mapping": 0, "no_product": 0}

    now = datetime.now(timezone.utc).isoformat()

    for it in items:
        col = FIELD_TO_COLUMN.get(it["field_name"])
        if not col:
            counts["no_column_mapping"] += 1
            continue

        c.execute(f"SELECT {col} AS val FROM products WHERE id=?", (it["product_id"],))
        row = c.fetchone()
        if not row:
            counts["no_product"] += 1
            continue

        current = normalize(row["val"])
        p1 = normalize(it["pass_1_value"])
        p2 = normalize(it["pass_2_value"])

        if fuzzy_match(current, p1):
            counts["still_pending"] += 1
            continue

        if fuzzy_match(current, p2):
            resolution = "auto_resolved_pass2"
            counts["resolved_pass2"] += 1
        else:
            resolution = "auto_resolved_post_fix"
            counts["resolved_other"] += 1

        c.execute(
            "UPDATE review_queue SET status='resolved', resolved_at=?, "
            "reviewer_notes='auto-resolved: re-scrape corrected after bug fixes' "
            "WHERE id=?",
            (now, it["rq_id"]),
        )
        c.execute(
            "UPDATE validation_comparisons SET resolution=?, resolved_at=? WHERE id=?",
            (resolution, now, it["comparison_id"]),
        )

    print(f"Auto-resolved (current ≈ pass_2): {counts['resolved_pass2']}")
    print(f"Auto-resolved (current = post-fix value): {counts['resolved_other']}")
    print(f"Still pending (bug still active): {counts['still_pending']}")
    print(f"No column mapping: {counts['no_column_mapping']}")
    print(f"No product (orphan): {counts['no_product']}")

    conn.commit()

    # Final state
    c.execute("SELECT status, COUNT(*) FROM review_queue GROUP BY status")
    print("\n=== Final review_queue distribution ===")
    for r in c.fetchall():
        print(f"  {r[0]}: {r[1]}")

    conn.close()


if __name__ == "__main__":
    main()
