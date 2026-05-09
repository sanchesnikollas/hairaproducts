"""LLM-based categorization for long-tail ingredients (Fase 1b Moon).

Sends batches of 30 uncategorized ingredients to Claude Haiku with a
structured prompt. Categories must match the rule-based taxonomy.

Strategy:
- Prioritize by usage descending (most impactful first)
- Batch size 30 (fits comfortably in Haiku context, fast)
- Min usage threshold (default 5)
- Skip ingredients already categorized

Usage:
  ANTHROPIC_API_KEY=... python scripts/llm_categorize_ingredients.py --dry-run
  ANTHROPIC_API_KEY=... python scripts/llm_categorize_ingredients.py --apply --min-usage 5
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
import sys
import time

DB = "haira.db"
BATCH_SIZE = 30
MODEL = "claude-haiku-4-5-20251001"

# Allowed categories — MUST match scripts/categorize_ingredients.py taxonomy
CATEGORIES = [
    "surfactant_anionic", "surfactant_amphoteric", "surfactant_cationic", "surfactant_nonionic",
    "silicone_volatile", "silicone_insoluble", "silicone_amine", "silicone_water_soluble",
    "oil_natural", "oil_mineral", "butter_natural",
    "fatty_alcohol", "fatty_acid", "alcohol_drying",
    "humectant", "protein", "active",
    "polymer_film", "polymer_cationic",
    "preservative", "chelator", "antioxidant", "ph_adjuster",
    "fragrance", "fragrance_allergen", "colorant",
    "exfoliant", "thickener", "electrolyte", "emulsifier",
    "emollient_synthetic", "extract_botanical", "absorbent", "solvent",
    "uv_filter",  # for sunscreens (octinoxate, avobenzone)
    "other",      # fallback for unknowns
]

PROMPT_TEMPLATE = """You are a cosmetics chemistry expert. Classify each ingredient by its primary functional role in hair-care products.

VALID CATEGORIES (use exact slug):
{categories}

For each ingredient, return ONLY the category slug. No explanations.

Format your response as a JSON object: {{"ingredient_name": "category_slug", ...}}

Ingredients to classify:
{ingredients_list}

Return only the JSON object, nothing else."""


def call_anthropic(client, batch: list[tuple[str, int]]) -> dict[str, str]:
    """Call Claude API and parse JSON response."""
    ing_list = "\n".join(f"- {name} (usage: {usage})" for name, usage in batch)
    prompt = PROMPT_TEMPLATE.format(
        categories="\n".join(f"  - {c}" for c in CATEGORIES),
        ingredients_list=ing_list,
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON
        import re
        m = re.search(r"\{.+\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        print(f"  WARN: failed to parse: {text[:200]}")
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-usage", type=int, default=5)
    ap.add_argument("--limit", type=int, default=2000)
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        print("Pass --dry-run or --apply")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    from anthropic import Anthropic
    client = Anthropic()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = list(conn.execute(f"""
        SELECT i.id, i.canonical_name, COUNT(pi.id) as usage
        FROM ingredients i
        LEFT JOIN product_ingredients pi ON pi.ingredient_id = i.id
        WHERE i.category IS NULL
        GROUP BY i.id
        HAVING usage >= {args.min_usage}
        ORDER BY usage DESC
        LIMIT {args.limit}
    """))
    print(f"To categorize: {len(rows)} ingredients (usage >= {args.min_usage})")

    if args.dry_run:
        print(f"Would send {(len(rows) + BATCH_SIZE - 1) // BATCH_SIZE} batches of {BATCH_SIZE}")
        print("\nFirst batch sample:")
        for r in rows[:10]:
            print(f"  {r['canonical_name']} (usage: {r['usage']})")
        return

    # Apply
    total_categorized = 0
    by_cat: dict[str, int] = {}
    invalid_cats = 0
    c = conn.cursor()

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]
        items = [(r["canonical_name"], r["usage"]) for r in batch]
        try:
            result = call_anthropic(client, items)
        except Exception as e:
            print(f"  Batch {batch_start//BATCH_SIZE+1}: API error {e}")
            time.sleep(5)
            continue

        # Apply to DB by canonical_name match
        applied = 0
        for r in batch:
            name = r["canonical_name"]
            cat = result.get(name) or result.get(name.lower()) or result.get(name.upper())
            if not cat:
                continue
            if cat not in CATEGORIES:
                invalid_cats += 1
                continue
            c.execute("UPDATE ingredients SET category = ? WHERE id = ?", (cat, r["id"]))
            applied += 1
            by_cat[cat] = by_cat.get(cat, 0) + 1
        conn.commit()
        total_categorized += applied
        print(f"  Batch {batch_start//BATCH_SIZE+1}/{(len(rows)+BATCH_SIZE-1)//BATCH_SIZE}: "
              f"{applied}/{len(batch)} categorized | running total: {total_categorized}",
              flush=True)
        time.sleep(0.5)

    conn.close()
    print(f"\n=== DONE ===")
    print(f"Total categorized: {total_categorized}")
    print(f"Invalid categories returned: {invalid_cats}")
    print(f"\nBy category:")
    for cat, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat:<30} {n:>5}")


if __name__ == "__main__":
    main()
