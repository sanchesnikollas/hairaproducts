"""Cleanup duplicate URLs (fragments, listing params, size variants) for any brand.

Uses the same normalize_discovery_url() rule as the live scraper, applied retroactively.
Strategy:
1. For each product whose URL would change after normalization:
   - If a canonical (already normalized) sibling exists: merge fields, move evidence,
     delete the duplicate
   - If no canonical sibling: rename the URL in-place to its normalized form
2. Pure listing pages (path with no .html and only listing params) are deleted
"""
from __future__ import annotations
import json
import re
import sqlite3
import sys

sys.path.insert(0, ".")
from src.discovery.url_classifier import normalize_discovery_url

DB_PATH = "haira.db"

SCALAR_FIELDS = [
    "inci_ingredients", "price", "description", "size_volume",
    "image_url_main", "product_category", "usage_instructions",
    "composition", "ph", "audience_age", "function_objective",
    "image_url_front", "image_url_back",
]
JSON_FIELDS = ["product_labels", "hair_type"]


def is_empty(v):
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def merge_json(canon_val, frag_val):
    try:
        cobj = json.loads(canon_val) if canon_val else None
    except (json.JSONDecodeError, TypeError):
        cobj = None
    try:
        fobj = json.loads(frag_val) if frag_val else None
    except (json.JSONDecodeError, TypeError):
        fobj = None
    if cobj is None and fobj is None:
        return None
    if cobj is None:
        return json.dumps(fobj, ensure_ascii=False)
    if fobj is None:
        return json.dumps(cobj, ensure_ascii=False)
    if isinstance(cobj, list) and isinstance(fobj, list):
        merged = list(cobj)
        for item in fobj:
            if item not in merged:
                merged.append(item)
        return json.dumps(merged, ensure_ascii=False)
    if isinstance(cobj, dict) and isinstance(fobj, dict):
        result = dict(fobj)
        result.update({k: v for k, v in cobj.items() if v is not None})
        return json.dumps(result, ensure_ascii=False)
    return json.dumps(cobj, ensure_ascii=False)


def is_pure_listing(url: str) -> bool:
    """A listing page that contains no actual product."""
    norm = normalize_discovery_url(url)
    if not norm:
        return False
    # No .html in path AND short path (likely a listing root)
    path = norm.split("?")[0].rstrip("/")
    if path.endswith(".html"):
        return False
    # Demandware-style /shampoos/, /conditioners/, /colecoes-linhas/, /descubra/...
    listing_indicators = ["/descubra/", "/conditioners", "/shampoos",
                          "/colecoes-linhas", "/condicionadores-e-mascaras",
                          "/kits-2", "/produtos/refil"]
    if any(seg in path for seg in listing_indicators):
        return True
    return False


def cleanup_brand(brand_slug: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("BEGIN")

    cols = ", ".join(SCALAR_FIELDS + JSON_FIELDS)
    c.execute(
        f"SELECT id, product_url, {cols} FROM products WHERE brand_slug=?",
        (brand_slug,),
    )
    all_products = c.fetchall()
    print(f"\n=== {brand_slug} ===")
    print(f"Before: {len(all_products)} products")

    # Group by normalized URL
    by_norm: dict[str, list] = {}
    listings_to_delete = []

    for p in all_products:
        norm = normalize_discovery_url(p["product_url"])
        if not norm:
            continue
        if is_pure_listing(p["product_url"]):
            listings_to_delete.append(p["id"])
            continue
        by_norm.setdefault(norm, []).append(p)

    fields_filled = 0
    pairs_merged = 0
    duplicates_to_delete = []
    renames = 0

    for norm_url, group in by_norm.items():
        if len(group) == 1:
            # Maybe the URL needs renaming (single entry but URL has fragment/tracking)
            p = group[0]
            if p["product_url"] != norm_url:
                # Check no canonical with that URL exists already (it shouldn't, since it's alone in group)
                c.execute("UPDATE products SET product_url=? WHERE id=?", (norm_url, p["id"]))
                renames += 1
            continue

        # Multiple entries for the same canonical URL → merge
        # Pick a "canonical" preference: URL exactly matching norm_url first, else any
        canon = next((p for p in group if p["product_url"] == norm_url), None)
        if canon is None:
            # Rename one to be the canonical, others are duplicates
            canon = group[0]
            c.execute("UPDATE products SET product_url=? WHERE id=?",
                      (norm_url, canon["id"]))
            renames += 1

        for dup in group:
            if dup["id"] == canon["id"]:
                continue
            pairs_merged += 1
            updates = []
            params = []
            # Re-read canonical (it may have changed in earlier iterations)
            c.execute(f"SELECT id, {cols} FROM products WHERE id=?", (canon["id"],))
            canon_fresh = c.fetchone()
            for field in SCALAR_FIELDS:
                if is_empty(canon_fresh[field]) and not is_empty(dup[field]):
                    updates.append(f"{field}=?")
                    params.append(dup[field])
                    fields_filled += 1
            for field in JSON_FIELDS:
                merged = merge_json(canon_fresh[field], dup[field])
                if merged is not None and merged != canon_fresh[field]:
                    updates.append(f"{field}=?")
                    params.append(merged)
            if updates:
                params.append(canon["id"])
                c.execute(
                    f"UPDATE products SET {', '.join(updates)} WHERE id=?",
                    params,
                )
            c.execute(
                "UPDATE product_evidence SET product_id=? WHERE product_id=?",
                (canon["id"], dup["id"]),
            )
            duplicates_to_delete.append(dup["id"])

    print(f"Listings to delete: {len(listings_to_delete)}")
    print(f"Duplicates to delete: {len(duplicates_to_delete)}")
    print(f"Renames in-place: {renames}")
    print(f"Pairs merged: {pairs_merged}, fields filled: {fields_filled}")

    ids_to_delete = listings_to_delete + duplicates_to_delete
    if ids_to_delete:
        ph = ",".join("?" * len(ids_to_delete))
        for tbl in ("quarantine_details", "validation_comparisons",
                    "review_queue", "product_images", "product_claims",
                    "product_compositions", "product_ingredients",
                    "enrichment_queue", "product_evidence"):
            c.execute(f"DELETE FROM {tbl} WHERE product_id IN ({ph})", ids_to_delete)
        c.execute(f"DELETE FROM products WHERE id IN ({ph})", ids_to_delete)
        print(f"Products deleted: {c.rowcount}")

    conn.commit()
    c.execute("SELECT COUNT(*) FROM products WHERE brand_slug=?", (brand_slug,))
    after = c.fetchone()[0]
    print(f"After: {after}")
    conn.close()
    return len(all_products), after


if __name__ == "__main__":
    if len(sys.argv) > 1:
        brands = sys.argv[1:]
    else:
        brands = [
            "joico", "arvensis-cosmeticos-naturais", "b-o-b-bars",
            "elseve", "hidratei", "widi-care", "acquaflora", "balai",
            "amazonico-care", "beleza-natural", "mustela", "seda",
            "eudora", "dove", "apice-cosmeticos", "b-hulmann",
            "lola-cosmetics", "alva",
        ]
    grand_before = 0
    grand_after = 0
    for b in brands:
        before, after = cleanup_brand(b)
        grand_before += before
        grand_after += after
    print(f"\n=== TOTAL ===")
    print(f"Before: {grand_before} | After: {grand_after} | Removed: {grand_before - grand_after}")
