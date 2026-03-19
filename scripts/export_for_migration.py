#!/usr/bin/env python3
"""Export non-amend brand data from local SQLite as PostgreSQL-compatible INSERT statements.

Usage:
    python3 scripts/export_for_migration.py > /tmp/migration.sql
    cat /tmp/migration.sql | railway connect postgres
"""
from __future__ import annotations

import json
import sys
import pathlib
import sqlite3

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "haira.db"

SKIP_BRANDS = {"amend"}  # already in production


def escape(val):
    """Escape a value for PostgreSQL INSERT."""
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    s = str(val).replace("'", "''")
    return f"'{s}'"


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def export_table(conn, table, where_clause="", params=(), id_col="id"):
    """Export rows as INSERT statements with ON CONFLICT DO NOTHING."""
    cursor = conn.cursor()
    cursor.row_factory = dict_factory
    sql = f"SELECT * FROM {table}"
    if where_clause:
        sql += f" WHERE {where_clause}"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    if not rows:
        return 0

    cols = list(rows[0].keys())
    col_names = ", ".join(cols)
    count = 0

    for row in rows:
        values = ", ".join(escape(row[c]) for c in cols)
        print(f"INSERT INTO {table} ({col_names}) VALUES ({values}) ON CONFLICT DO NOTHING;")
        count += 1

    return count


def main():
    conn = sqlite3.connect(str(DB_PATH))

    # Get brands to migrate
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT brand_slug FROM products")
    all_brands = [r[0] for r in cursor.fetchall()]
    brands = [b for b in all_brands if b not in SKIP_BRANDS]

    if not brands:
        print("-- No new brands to migrate", file=sys.stderr)
        return

    print(f"-- Migrating brands: {', '.join(brands)}", file=sys.stderr)
    print("BEGIN;")

    # 1. Products
    placeholders = ",".join(["?"] * len(brands))
    n = export_table(conn, "products", f"brand_slug IN ({placeholders})", tuple(brands))
    print(f"-- products: {n}", file=sys.stderr)

    # Get product IDs for these brands
    cursor.execute(f"SELECT id FROM products WHERE brand_slug IN ({placeholders})", tuple(brands))
    product_ids = [r[0] for r in cursor.fetchall()]

    if not product_ids:
        print("COMMIT;")
        return

    # Process in chunks to avoid SQL limits
    def chunked_export(table, id_field="product_id"):
        total = 0
        for i in range(0, len(product_ids), 500):
            chunk = product_ids[i : i + 500]
            ph = ",".join(["?"] * len(chunk))
            total += export_table(conn, table, f"{id_field} IN ({ph})", tuple(chunk))
        return total

    # 2. Evidence
    n = chunked_export("product_evidence")
    print(f"-- product_evidence: {n}", file=sys.stderr)

    # 3. Quarantine
    n = chunked_export("quarantine_details")
    print(f"-- quarantine_details: {n}", file=sys.stderr)

    # 4. Ingredients (need to find which ones are referenced)
    cursor.execute(f"""
        SELECT DISTINCT pi.ingredient_id FROM product_ingredients pi
        JOIN products p ON pi.product_id = p.id
        WHERE p.brand_slug IN ({placeholders})
    """, tuple(brands))
    ingredient_ids = [r[0] for r in cursor.fetchall()]

    if ingredient_ids:
        for i in range(0, len(ingredient_ids), 500):
            chunk = ingredient_ids[i : i + 500]
            ph = ",".join(["?"] * len(chunk))
            export_table(conn, "ingredients", f"id IN ({ph})", tuple(chunk))
            export_table(conn, "ingredient_aliases", f"ingredient_id IN ({ph})", tuple(chunk))
        print(f"-- ingredients: {len(ingredient_ids)}", file=sys.stderr)

    # 5. Product ingredients
    n = chunked_export("product_ingredients")
    print(f"-- product_ingredients: {n}", file=sys.stderr)

    # 6. Claims
    cursor.execute(f"""
        SELECT DISTINCT pc.claim_id FROM product_claims pc
        JOIN products p ON pc.product_id = p.id
        WHERE p.brand_slug IN ({placeholders})
    """, tuple(brands))
    claim_ids = [r[0] for r in cursor.fetchall()]

    if claim_ids:
        for i in range(0, len(claim_ids), 500):
            chunk = claim_ids[i : i + 500]
            ph = ",".join(["?"] * len(chunk))
            export_table(conn, "claims", f"id IN ({ph})", tuple(chunk))
            export_table(conn, "claim_aliases", f"claim_id IN ({ph})", tuple(chunk))

    n = chunked_export("product_claims")
    print(f"-- product_claims: {n}", file=sys.stderr)

    # 7. Images
    n = chunked_export("product_images")
    print(f"-- product_images: {n}", file=sys.stderr)

    # 8. Compositions
    n = chunked_export("product_compositions")
    print(f"-- product_compositions: {n}", file=sys.stderr)

    # 9. Brand coverage
    n = export_table(conn, "brand_coverage", f"brand_slug IN ({placeholders})", tuple(brands))
    print(f"-- brand_coverage: {n}", file=sys.stderr)

    print("COMMIT;")
    conn.close()
    print(f"-- Done! Total brands: {len(brands)}", file=sys.stderr)


if __name__ == "__main__":
    main()
