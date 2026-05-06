"""Cleanup products with junk product_name extracted from generic listing/error pages.

These are pages where extraction picked up site UI text (cart, login, error)
instead of actual product info. They have the brand_slug set but no real product data.

Common junk patterns (Portuguese):
  - "Não existem produtos..." (empty category/brand pages)
  - "Ops :(" (error pages)
  - "Carrinho..." (cart pages, but NOT "Carrinho auxiliar*" which is a real salon trolley)
  - "Identificação...login..." (login pages)
  - "Politica*", "Como Comprar*", "Frete*", "Formas de Pagamento|Entrega" — info pages

Usage:
  python scripts/cleanup_junk_product_names.py --dry-run
  python scripts/cleanup_junk_product_names.py --apply
"""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

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

JUNK_QUERY = """
SELECT id, brand_slug, product_name FROM products
WHERE product_name LIKE 'Não existem produtos%'
   OR product_name = 'Ops :('
   OR (product_name LIKE 'Carrinho%' AND product_name NOT LIKE 'Carrinho auxiliar%')
   OR product_name LIKE 'Identificação%cadastro%'
   OR product_name LIKE 'IdentificaçãoFaça o seu login%'
   OR product_name LIKE 'Politica %'
   OR product_name LIKE 'Como Comprar%'
   OR product_name LIKE 'Frete %'
   OR product_name LIKE 'Formas de %'
   OR product_name LIKE 'Duvidas %'
   OR product_name = 'Como comprar'
"""


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--apply" not in args
    if dry_run and "--dry-run" not in args:
        print("Pass --dry-run or --apply explicitly.")
        sys.exit(2)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rows = list(c.execute(JUNK_QUERY))
    if not rows:
        print("No junk products found.")
        return

    by_brand: dict[str, int] = {}
    for r in rows:
        by_brand[r["brand_slug"]] = by_brand.get(r["brand_slug"], 0) + 1
    print(f"Found {len(rows)} junk products across {len(by_brand)} brands:")
    for b, n in sorted(by_brand.items(), key=lambda x: -x[1]):
        print(f"  {b:<35} {n:>4}")

    if dry_run:
        print(f"\nDRY-RUN: pass --apply to delete.")
        print("Sample (first 10):")
        for r in rows[:10]:
            print(f"  [{r['brand_slug']}] {r['product_name'][:80]}")
        conn.close()
        return

    ids = [r["id"] for r in rows]
    placeholders = ",".join("?" * len(ids))
    c.execute("BEGIN")
    for tbl in CHILD_TABLES:
        c.execute(f"DELETE FROM {tbl} WHERE product_id IN ({placeholders})", ids)
    c.execute(f"DELETE FROM products WHERE id IN ({placeholders})", ids)
    deleted = c.rowcount
    conn.commit()
    conn.close()
    print(f"\nDeleted {deleted} junk products.")


if __name__ == "__main__":
    main()
