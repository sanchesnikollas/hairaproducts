"""
Batch enrichment script for HAIRA products.

Fills missing fields:
  1. size_volume   — regex from product_name, description, composition
  2. product_category — from product_type_normalized or product_name keywords
  3. description   — from product_evidence rows
  4. image_url_main — from product_images table or image_urls_gallery JSON
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_URL = "sqlite:///haira.db"

# Volume regex — matches patterns like 500ml, 1,5L, 250 G, 12oz, etc.
SIZE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?\s*(?:ml|g|kg|l|oz|lt))\b",
    re.IGNORECASE,
)

# Mapping from product_type_normalized -> product_category
TYPE_TO_CATEGORY = {
    "shampoo": "shampoo",
    "conditioner": "condicionador",
    "mask": "mascara",
    "leave_in": "leave-in",
    "oil_serum": "oleo",
    "oil": "oleo",
    "serum": "serum",
    "spray": "spray",
    "cream": "creme",
    "gel": "gel",
    "balm": "balsamo",
    "tonic": "tonico",
    "coloracao": "coloracao",
    "kit": "kit",
    "reconstructor": "reconstrutor",
    "reparador": "reparador",
    "ativador": "ativador",
    "finisher": "finalizador",
    "relaxante": "relaxante",
    "oxidante": "oxidante",
    "treatment": "tratamento",
    "mousse": "mousse",
    "protetor": "protetor-termico",
}

# Keyword matching in product_name (Portuguese & English)
NAME_KEYWORDS: dict[str, str] = {
    "shampoo": "shampoo",
    "condicionador": "condicionador",
    "conditioner": "condicionador",
    "máscara": "mascara",
    "mascara": "mascara",
    "mask": "mascara",
    "leave-in": "leave-in",
    "leave in": "leave-in",
    "óleo": "oleo",
    "oleo": "oleo",
    "oil": "oleo",
    "sérum": "serum",
    "serum": "serum",
    "spray": "spray",
    "creme": "creme",
    "cream": "creme",
    "gel": "gel",
    "bálsamo": "balsamo",
    "balsamo": "balsamo",
    "tônico": "tonico",
    "tonico": "tonico",
    "coloração": "coloracao",
    "coloracao": "coloracao",
    "tonalizante": "tonalizante",
    "finalizador": "finalizador",
    "ampola": "ampola",
    "protetor": "protetor-termico",
    "mousse": "mousse",
    "ativador": "ativador",
    "pomada": "pomada",
    "reconstructor": "reconstrutor",
    "reconstrutor": "reconstrutor",
    "reconstrução": "reconstrutor",
}


def _extract_volume(name: str, description: str | None, composition: str | None) -> str | None:
    """Try to extract volume from name first, then description, then composition."""
    for source in (name, description, composition):
        if source:
            m = SIZE_RE.search(source)
            if m:
                return m.group(1).strip()
    return None


def _infer_category(product_type_normalized: str | None, product_name: str) -> str | None:
    """Infer product_category from type_normalized or name keywords."""
    # First try the normalized type
    if product_type_normalized:
        cat = TYPE_TO_CATEGORY.get(product_type_normalized)
        if cat:
            return cat

    # Fall back to keyword matching in the name
    name_lower = product_name.lower()
    # Check multi-word keywords first (leave-in, leave in)
    for kw in sorted(NAME_KEYWORDS, key=len, reverse=True):
        if kw in name_lower:
            return NAME_KEYWORDS[kw]

    return None


def main() -> None:
    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()

        # --- BEFORE stats ---
        def _pct(field: str) -> tuple[int, float]:
            n = conn.execute(
                text(f"SELECT COUNT(*) FROM products WHERE {field} IS NOT NULL AND {field} != ''")
            ).scalar()
            return n, (n / total * 100) if total else 0.0

        stats_before = {
            "description": _pct("description"),
            "image_url_main": _pct("image_url_main"),
            "usage_instructions": _pct("usage_instructions"),
            "size_volume": _pct("size_volume"),
            "product_category": _pct("product_category"),
        }

        print(f"Total products: {total}")
        print("\n=== BEFORE ===")
        for field, (n, pct) in stats_before.items():
            print(f"  {field}: {n}/{total} = {pct:.1f}%")

        # ---------------------------------------------------------------
        # Step 1: size_volume — regex from name/description/composition
        # ---------------------------------------------------------------
        rows = conn.execute(
            text("""
                SELECT id, product_name, description, composition
                FROM products
                WHERE size_volume IS NULL OR size_volume = ''
            """)
        ).fetchall()

        vol_updates = 0
        for pid, name, desc, comp in rows:
            vol = _extract_volume(name, desc, comp)
            if vol:
                conn.execute(
                    text("UPDATE products SET size_volume = :vol, updated_at = :now WHERE id = :id"),
                    {"vol": vol, "now": datetime.now(timezone.utc).isoformat(), "id": pid},
                )
                vol_updates += 1

        print(f"\n[Step 1] size_volume: enriched {vol_updates} products")

        # ---------------------------------------------------------------
        # Step 2: product_category — from type_normalized or name keywords
        # ---------------------------------------------------------------
        rows = conn.execute(
            text("""
                SELECT id, product_type_normalized, product_name
                FROM products
                WHERE product_category IS NULL OR product_category = ''
            """)
        ).fetchall()

        cat_updates = 0
        for pid, ptype, pname in rows:
            cat = _infer_category(ptype, pname)
            if cat:
                conn.execute(
                    text("UPDATE products SET product_category = :cat, updated_at = :now WHERE id = :id"),
                    {"cat": cat, "now": datetime.now(timezone.utc).isoformat(), "id": pid},
                )
                cat_updates += 1

        print(f"[Step 2] product_category: enriched {cat_updates} products")

        # ---------------------------------------------------------------
        # Step 3: description — from product_evidence
        # ---------------------------------------------------------------
        rows = conn.execute(
            text("""
                SELECT p.id, pe.raw_source_text
                FROM products p
                JOIN product_evidence pe ON pe.product_id = p.id
                WHERE (p.description IS NULL OR p.description = '')
                  AND pe.field_name = 'description'
                  AND pe.raw_source_text IS NOT NULL
                  AND pe.raw_source_text != ''
                ORDER BY pe.extracted_at DESC
            """)
        ).fetchall()

        desc_updates = 0
        seen_ids: set[str] = set()
        for pid, raw_text in rows:
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            conn.execute(
                text("UPDATE products SET description = :desc, updated_at = :now WHERE id = :id"),
                {"desc": raw_text.strip(), "now": datetime.now(timezone.utc).isoformat(), "id": pid},
            )
            desc_updates += 1

        print(f"[Step 3] description: enriched {desc_updates} products from evidence")

        # ---------------------------------------------------------------
        # Step 4: image_url_main — from product_images or gallery JSON
        # ---------------------------------------------------------------
        # 4a: from product_images table
        rows = conn.execute(
            text("""
                SELECT p.id, pi.url
                FROM products p
                JOIN product_images pi ON pi.product_id = p.id
                WHERE (p.image_url_main IS NULL OR p.image_url_main = '')
                ORDER BY pi.position ASC
            """)
        ).fetchall()

        img_updates = 0
        seen_ids = set()
        for pid, url in rows:
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            conn.execute(
                text("UPDATE products SET image_url_main = :url, updated_at = :now WHERE id = :id"),
                {"url": url, "now": datetime.now(timezone.utc).isoformat(), "id": pid},
            )
            img_updates += 1

        # 4b: from image_urls_gallery JSON for remaining
        rows = conn.execute(
            text("""
                SELECT id, image_urls_gallery
                FROM products
                WHERE (image_url_main IS NULL OR image_url_main = '')
                  AND image_urls_gallery IS NOT NULL
            """)
        ).fetchall()

        for pid, gallery_json in rows:
            try:
                gallery = json.loads(gallery_json) if isinstance(gallery_json, str) else gallery_json
                if isinstance(gallery, list) and gallery:
                    url = gallery[0] if isinstance(gallery[0], str) else gallery[0].get("url", "")
                    if url:
                        conn.execute(
                            text("UPDATE products SET image_url_main = :url, updated_at = :now WHERE id = :id"),
                            {"url": url, "now": datetime.now(timezone.utc).isoformat(), "id": pid},
                        )
                        img_updates += 1
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        print(f"[Step 4] image_url_main: enriched {img_updates} products")

        # Commit all changes
        conn.commit()

        # --- AFTER stats ---
        print("\n=== AFTER ===")
        stats_after = {
            "description": _pct("description"),
            "image_url_main": _pct("image_url_main"),
            "usage_instructions": _pct("usage_instructions"),
            "size_volume": _pct("size_volume"),
            "product_category": _pct("product_category"),
        }
        for field, (n, pct) in stats_after.items():
            before_n, before_pct = stats_before[field]
            delta = n - before_n
            marker = f" (+{delta})" if delta > 0 else ""
            print(f"  {field}: {n}/{total} = {pct:.1f}%{marker}")

        print("\n=== SUMMARY ===")
        print(f"  size_volume:      +{vol_updates}")
        print(f"  product_category: +{cat_updates}")
        print(f"  description:      +{desc_updates}")
        print(f"  image_url_main:   +{img_updates}")
        print(f"  Total enriched fields: {vol_updates + cat_updates + desc_updates + img_updates}")


if __name__ == "__main__":
    main()
