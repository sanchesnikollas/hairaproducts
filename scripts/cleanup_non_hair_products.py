"""Mark or remove products that are clearly non-hair based on product_name patterns.

Default mode: marks `hair_relevance_reason='non_hair_by_name'` (soft).
With --delete: hard-deletes (with cascade).

Usage:
  python scripts/cleanup_non_hair_products.py --dry-run [brand_slug ...]
  python scripts/cleanup_non_hair_products.py [brand_slug ...]
  python scripts/cleanup_non_hair_products.py --delete [brand_slug ...]
"""
from __future__ import annotations
import sqlite3
import sys

DB = "haira.db"

NON_HAIR_PATTERNS = [
    "base ", "batom", "blush", "lápis ", "lapis ", "esmalte", "perfume",
    "colônia", "colonia", "eau de", "body splash", "protetor solar",
    "hidratante facial", "creme facial", "sérum facial", "serum facial",
    "cílios", "cilios", "rímel", "rimel", "sombra", "delineador",
    "desodorante", "antitranspirante", "depilatório", "depilatorio",
    "sabonete corporal", "sabonete liquido", "loção corporal", "locao corporal",
    "creme corporal", "óleo corporal", "oleo corporal", "creme para mãos",
    "creme para maos", "creme dental", "pasta dental", "enxaguante bucal",
    "talco", "fralda", "pomada infantil", "máscara facial", "mascara facial",
    "tônico facial", "tonico facial",
]

CHILD_TABLES = (
    "product_evidence", "quarantine_details", "validation_comparisons",
    "review_queue", "product_images", "product_claims", "product_compositions",
    "product_ingredients", "enrichment_queue",
)


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    delete_mode = "--delete" in args
    brands = [a for a in args if not a.startswith("--")]

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    where_brand = ""
    params: list = []
    if brands:
        where_brand = f"AND brand_slug IN ({','.join('?' for _ in brands)})"
        params = brands[:]

    pattern_ors = " OR ".join("LOWER(product_name) LIKE ?" for _ in NON_HAIR_PATTERNS)
    sql = f"""SELECT id, brand_slug, product_name FROM products
              WHERE ({pattern_ors}) {where_brand}"""
    c.execute(sql, [f"%{p}%" for p in NON_HAIR_PATTERNS] + params)
    rows = c.fetchall()
    print(f"Matched {len(rows)} products as non-hair")

    by_brand: dict[str, int] = {}
    for _, slug, _ in rows:
        by_brand[slug] = by_brand.get(slug, 0) + 1
    print("Top brands affected:")
    for slug, n in sorted(by_brand.items(), key=lambda x: -x[1])[:15]:
        print(f"  {slug}: {n}")

    if dry_run:
        print("DRY-RUN, no changes")
        # Sample matched names
        print("\nSample matched names (10):")
        for _, slug, name in rows[:10]:
            print(f"  [{slug}] {name[:80]}")
        return

    ids = [r[0] for r in rows]
    if not ids:
        print("Nothing to do")
        return

    if delete_mode:
        for tbl in CHILD_TABLES:
            placeholders = ",".join("?" for _ in ids)
            try:
                c.execute(f"DELETE FROM {tbl} WHERE product_id IN ({placeholders})", ids)
            except sqlite3.OperationalError:
                pass
        c.execute(
            f"DELETE FROM products WHERE id IN ({','.join('?' for _ in ids)})", ids
        )
        print(f"Deleted {len(ids)} products + cascade")
    else:
        c.execute(
            f"UPDATE products SET hair_relevance_reason='non_hair_by_name' WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
        )
        print(f"Marked {len(ids)} products as non_hair_by_name")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
