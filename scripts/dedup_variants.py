"""Deduplicate products by (brand_slug, product_name, size_volume).

For brands like griffus/brae, the same product (same name + size) appears many times
because discovery indexes category/listing pages and the extractor picks up the
featured product name from each.

Strategy: for each (brand, name, size) group with >1 row, keep the row with the
"richest" fill (most non-null fields, prefer verified_inci, has price, has inci).
Delete the rest along with their child rows.

Usage:
  python scripts/dedup_variants.py --dry-run
  python scripts/dedup_variants.py --apply
  python scripts/dedup_variants.py --apply --brand griffus
"""
from __future__ import annotations
import argparse
import sqlite3

DB_PATH = "haira.db"

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


def score(row: sqlite3.Row) -> int:
    """Higher = better."""
    s = 0
    if row["verification_status"] == "verified_inci":
        s += 1000
    if row["inci_ingredients"] and row["inci_ingredients"] not in ("[]", "null"):
        s += 500
    if row["price"] is not None:
        s += 100
    if row["description"]:
        s += 50
    if row["image_url_main"]:
        s += 25
    if row["product_url"] and "/produto" in row["product_url"]:
        s += 200  # actual product URL beats listing page
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--brand", default=None)
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        print("Pass --dry-run or --apply")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    where = "WHERE 1=1"
    params: list = []
    if args.brand:
        where += " AND brand_slug = ?"
        params.append(args.brand)

    # Find groups with >1 product
    groups = list(c.execute(
        f"""SELECT brand_slug, product_name, COALESCE(size_volume, '') as sz, COUNT(*) as n
            FROM products
            {where}
            GROUP BY brand_slug, product_name, COALESCE(size_volume, '')
            HAVING n > 1""", params))
    print(f"Groups with >1 row: {len(groups)}")

    total_keep = len(groups)
    total_delete = 0
    delete_ids: list[str] = []

    for g in groups:
        rows = list(c.execute(
            """SELECT id, brand_slug, product_url, product_name, size_volume,
                      verification_status, inci_ingredients, price, description, image_url_main
               FROM products
               WHERE brand_slug=? AND product_name=? AND COALESCE(size_volume,'')=?""",
            (g["brand_slug"], g["product_name"], g["sz"]),
        ))
        ranked = sorted(rows, key=score, reverse=True)
        keep = ranked[0]
        for r in ranked[1:]:
            delete_ids.append(r["id"])
            total_delete += 1

    print(f"Total to keep: {total_keep}")
    print(f"Total to delete: {total_delete}")

    if not delete_ids:
        return

    if args.dry_run:
        # Show top 5 by brand
        from collections import Counter
        by_brand = Counter()
        for g in groups:
            by_brand[g["brand_slug"]] += g["n"] - 1
        print("\nDeletes by brand (top 10):")
        for b, n in by_brand.most_common(10):
            print(f"  {b}: -{n}")
        print("\nDRY-RUN: pass --apply to delete.")
        return

    c.execute("BEGIN")
    BATCH = 500
    for i in range(0, len(delete_ids), BATCH):
        batch = delete_ids[i:i + BATCH]
        ph = ",".join("?" * len(batch))
        for tbl in CHILD_TABLES:
            try:
                c.execute(f"DELETE FROM {tbl} WHERE product_id IN ({ph})", batch)
            except sqlite3.OperationalError:
                pass  # table may not exist
        c.execute(f"DELETE FROM products WHERE id IN ({ph})", batch)
    conn.commit()
    print(f"\nDeleted {total_delete} duplicate rows.")


if __name__ == "__main__":
    main()
