#!/usr/bin/env python3
"""Export local SQLite data as JSON for migration to production.

Usage:
    python3 scripts/export_json_migration.py > /tmp/migration.json
"""
from __future__ import annotations

import json
import sys
import pathlib
import sqlite3

DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "haira.db"
SKIP_BRANDS = {"amend"}


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def export_table(conn, table, where="", params=()):
    cursor = conn.cursor()
    cursor.row_factory = dict_factory
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    cursor.execute(sql, params)
    return cursor.fetchall()


def main():
    conn = sqlite3.connect(str(DB_PATH))

    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT brand_slug FROM products")
    all_brands = [r[0] for r in cursor.fetchall()]
    brands = [b for b in all_brands if b not in SKIP_BRANDS]

    if not brands:
        print("No new brands to migrate", file=sys.stderr)
        return

    print(f"Migrating brands: {', '.join(brands)}", file=sys.stderr)

    ph = ",".join(["?"] * len(brands))
    data = {}

    # Products
    data["products"] = export_table(conn, "products", f"brand_slug IN ({ph})", tuple(brands))
    print(f"products: {len(data['products'])}", file=sys.stderr)

    product_ids = [p["id"] for p in data["products"]]

    def chunked_export(table, id_field="product_id"):
        rows = []
        for i in range(0, len(product_ids), 500):
            chunk = product_ids[i:i + 500]
            p = ",".join(["?"] * len(chunk))
            rows.extend(export_table(conn, table, f"{id_field} IN ({p})", tuple(chunk)))
        return rows

    # Evidence
    data["product_evidence"] = chunked_export("product_evidence")
    print(f"product_evidence: {len(data['product_evidence'])}", file=sys.stderr)

    # Quarantine
    data["quarantine_details"] = chunked_export("quarantine_details")
    print(f"quarantine_details: {len(data['quarantine_details'])}", file=sys.stderr)

    # Ingredients
    cursor.execute(f"""
        SELECT DISTINCT pi.ingredient_id FROM product_ingredients pi
        JOIN products p ON pi.product_id = p.id
        WHERE p.brand_slug IN ({ph})
    """, tuple(brands))
    ingredient_ids = [r[0] for r in cursor.fetchall()]

    if ingredient_ids:
        ing_rows = []
        alias_rows = []
        for i in range(0, len(ingredient_ids), 500):
            chunk = ingredient_ids[i:i + 500]
            p = ",".join(["?"] * len(chunk))
            ing_rows.extend(export_table(conn, "ingredients", f"id IN ({p})", tuple(chunk)))
            alias_rows.extend(export_table(conn, "ingredient_aliases", f"ingredient_id IN ({p})", tuple(chunk)))
        data["ingredients"] = ing_rows
        data["ingredient_aliases"] = alias_rows
    else:
        data["ingredients"] = []
        data["ingredient_aliases"] = []
    print(f"ingredients: {len(data['ingredients'])}, aliases: {len(data['ingredient_aliases'])}", file=sys.stderr)

    # Product ingredients
    data["product_ingredients"] = chunked_export("product_ingredients")
    print(f"product_ingredients: {len(data['product_ingredients'])}", file=sys.stderr)

    # Claims
    cursor.execute(f"""
        SELECT DISTINCT pc.claim_id FROM product_claims pc
        JOIN products p ON pc.product_id = p.id
        WHERE p.brand_slug IN ({ph})
    """, tuple(brands))
    claim_ids = [r[0] for r in cursor.fetchall()]

    if claim_ids:
        claim_rows = []
        claim_alias_rows = []
        for i in range(0, len(claim_ids), 500):
            chunk = claim_ids[i:i + 500]
            p = ",".join(["?"] * len(chunk))
            claim_rows.extend(export_table(conn, "claims", f"id IN ({p})", tuple(chunk)))
            claim_alias_rows.extend(export_table(conn, "claim_aliases", f"claim_id IN ({p})", tuple(chunk)))
        data["claims"] = claim_rows
        data["claim_aliases"] = claim_alias_rows
    else:
        data["claims"] = []
        data["claim_aliases"] = []
    print(f"claims: {len(data['claims'])}, claim_aliases: {len(data['claim_aliases'])}", file=sys.stderr)

    # Product claims
    data["product_claims"] = chunked_export("product_claims")
    print(f"product_claims: {len(data['product_claims'])}", file=sys.stderr)

    # Images
    data["product_images"] = chunked_export("product_images")
    print(f"product_images: {len(data['product_images'])}", file=sys.stderr)

    # Compositions
    data["product_compositions"] = chunked_export("product_compositions")
    print(f"product_compositions: {len(data['product_compositions'])}", file=sys.stderr)

    # Brand coverage
    data["brand_coverage"] = export_table(conn, "brand_coverage", f"brand_slug IN ({ph})", tuple(brands))
    print(f"brand_coverage: {len(data['brand_coverage'])}", file=sys.stderr)

    conn.close()

    json.dump(data, sys.stdout, ensure_ascii=False, default=str)
    print(f"\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
