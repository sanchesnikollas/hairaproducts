"""Second pass auto-resolve for INCI items where Pass 2 LLM incorrectly split
multilingual names like 'Aqua / Water / Eau' into separate ingredients.

Logic:
1. Tokenize both current INCI and Pass 2 by splitting on /, (), and commas
2. Build sets of normalized tokens (lowercase, alphanumeric only, > 2 chars)
3. If overlap ratio >= 0.8 (most ingredients match), treat as semantic match
   and resolve as 'kept_pass_1' (current is the canonical INCI standard format)
"""
from __future__ import annotations
import json
import re
import sqlite3
from datetime import datetime, timezone

DB_PATH = "haira.db"


def tokenize_inci(value) -> set:
    """Extract a set of normalized ingredient name tokens."""
    if not value:
        return set()
    items = []
    if isinstance(value, str):
        try:
            items = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            items = [value]
    if not isinstance(items, list):
        return set()
    tokens = set()
    for item in items:
        if not isinstance(item, str):
            continue
        # Split on /, (), commas, bullets
        parts = re.split(r"[/(),•·●;]", item)
        for p in parts:
            normalized = re.sub(r"[^a-z0-9]+", "", p.lower().strip())
            if len(normalized) >= 3:
                tokens.add(normalized)
    return tokens


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("BEGIN")

    c.execute("""
        SELECT rq.id AS rq_id, rq.product_id, rq.comparison_id,
               vc.pass_2_value, p.inci_ingredients AS current
        FROM review_queue rq
        JOIN validation_comparisons vc ON rq.comparison_id = vc.id
        JOIN products p ON rq.product_id = p.id
        WHERE rq.status = 'pending' AND rq.field_name = 'inci_ingredients'
    """)
    items = c.fetchall()
    print(f"Pending INCI: {len(items)}")

    resolved = 0
    kept = 0
    now = datetime.now(timezone.utc).isoformat()

    for it in items:
        current_tokens = tokenize_inci(it["current"])
        p2_tokens = tokenize_inci(it["pass_2_value"])
        if not current_tokens or not p2_tokens:
            kept += 1
            continue

        intersect = current_tokens & p2_tokens
        p2_coverage = len(intersect) / len(p2_tokens) if p2_tokens else 0
        cur_coverage = len(intersect) / len(current_tokens) if current_tokens else 0

        # Two acceptance cases:
        # (a) Current is a superset of Pass 2 (LLM truncated): p2_coverage >= 0.9
        #     means current contains essentially all P2 ingredients plus more.
        # (b) Mostly mutual coverage: both sides >= 0.7 (formatting differences).
        case_a = p2_coverage >= 0.9 and len(current_tokens) >= len(p2_tokens)
        case_b = p2_coverage >= 0.7 and cur_coverage >= 0.7
        if case_a or case_b:
            c.execute(
                "UPDATE review_queue SET status='resolved', resolved_at=?, "
                "reviewer_notes='auto: INCI multilingual format match (kept current)' "
                "WHERE id=?",
                (now, it["rq_id"]),
            )
            c.execute(
                "UPDATE validation_comparisons SET resolution='kept_pass_1', resolved_at=? WHERE id=?",
                (now, it["comparison_id"]),
            )
            resolved += 1
        else:
            kept += 1

    print(f"Resolved (semantic match): {resolved}")
    print(f"Kept pending: {kept}")

    conn.commit()
    c.execute("SELECT status, COUNT(*) FROM review_queue GROUP BY status")
    print("\n=== Final review_queue ===")
    for r in c.fetchall():
        print(f"  {r[0]}: {r[1]}")
    conn.close()


if __name__ == "__main__":
    main()
