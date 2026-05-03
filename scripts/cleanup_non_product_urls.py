"""Generic listing-page cleanup using each brand's product_url_pattern.

Reads config/blueprints/{brand}.yaml, gets the product_url_pattern regex,
and deletes products whose URL doesn't match that pattern. These are
listing/category pages accidentally captured during DOM crawl.

For each removed URL: cascades child rows (evidence, quarantine, review_queue,
validation_comparisons, etc.) atomically.

Usage:
  python scripts/cleanup_non_product_urls.py [brand_slug ...]
  python scripts/cleanup_non_product_urls.py --dry-run [brand_slug ...]
"""
from __future__ import annotations
import re
import sqlite3
import sys
import yaml
from pathlib import Path

DB_PATH = "haira.db"
BLUEPRINT_DIR = Path("config/blueprints")

CHILD_TABLES = (
    "product_evidence",
    "quarantine_details",
    "validation_comparisons",
    "review_queue",
    "product_images",
    "product_claims",
    "product_compositions",
    "product_ingredients",
    "enrichment_queue",
)


def load_pattern(brand_slug: str) -> str | None:
    bp_path = BLUEPRINT_DIR / f"{brand_slug}.yaml"
    if not bp_path.exists():
        return None
    with open(bp_path) as f:
        bp = yaml.safe_load(f)
    return bp.get("discovery", {}).get("product_url_pattern")


def cleanup_brand(brand_slug: str, dry_run: bool = False) -> tuple[int, int]:
    pattern_str = load_pattern(brand_slug)
    if not pattern_str:
        print(f"  {brand_slug}: no product_url_pattern in blueprint, skipping")
        return 0, 0
    pattern = re.compile(pattern_str)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute(
        "SELECT id, product_url FROM products WHERE brand_slug=?",
        (brand_slug,),
    )
    all_products = c.fetchall()
    total = len(all_products)

    bad_ids = [p["id"] for p in all_products if not pattern.search(p["product_url"])]

    if not bad_ids:
        print(f"  {brand_slug}: {total} products, all match pattern ✓")
        conn.close()
        return total, 0

    print(f"  {brand_slug}: {total} products, {len(bad_ids)} non-product URLs detected")
    if dry_run:
        for pid in bad_ids[:5]:
            c.execute("SELECT product_url FROM products WHERE id=?", (pid,))
            row = c.fetchone()
            print(f"    sample: {row['product_url'][:100]}")
        if len(bad_ids) > 5:
            print(f"    ... and {len(bad_ids) - 5} more")
        conn.close()
        return total, len(bad_ids)

    c.execute("BEGIN")
    placeholders = ",".join("?" * len(bad_ids))
    for tbl in CHILD_TABLES:
        c.execute(f"DELETE FROM {tbl} WHERE product_id IN ({placeholders})", bad_ids)
    c.execute(f"DELETE FROM products WHERE id IN ({placeholders})", bad_ids)
    deleted = c.rowcount
    conn.commit()
    conn.close()
    return total, deleted


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    if dry_run:
        args.remove("--dry-run")

    if args:
        brands = args
    else:
        # All brands with a blueprint
        brands = sorted(p.stem for p in BLUEPRINT_DIR.glob("*.yaml"))

    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    print(f"Brands to process: {len(brands)}")
    print()

    grand_total = 0
    grand_deleted = 0
    for b in brands:
        total, deleted = cleanup_brand(b, dry_run=dry_run)
        grand_total += total
        grand_deleted += deleted

    print(f"\n=== TOTAL ===")
    print(f"Products inspected: {grand_total}")
    print(f"Non-product URLs {'would be removed' if dry_run else 'removed'}: {grand_deleted}")


if __name__ == "__main__":
    main()
