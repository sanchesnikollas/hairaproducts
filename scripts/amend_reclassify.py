"""Reclassify all Amend products: is_kit, product_type_normalized, product_category."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.taxonomy import normalize_product_type, normalize_category, is_kit_url
from src.storage.orm_models import ProductORM

BRAND = "amend"

KIT_NAME_PATTERNS = [
    "kit ", "kit-", " | 2 produtos", " | 3 produtos", " | 4 produtos",
    " | 5 produtos", " | 6 produtos",
]


def is_kit_by_name(name: str) -> bool:
    lower = name.lower()
    return any(p in lower for p in KIT_NAME_PATTERNS)


def main() -> None:
    engine = create_engine("sqlite:///haira.db")
    with Session(engine) as session:
        products = session.query(ProductORM).filter(ProductORM.brand_slug == BRAND).all()
        print(f"Total products: {len(products)}")

        stats = {
            "kit_flagged": 0,
            "type_updated": 0,
            "category_updated": 0,
            "error_quarantined": 0,
            "still_no_type": 0,
        }

        for p in products:
            name = p.product_name or ""
            url = p.product_url or ""

            # 1. Flag kits
            kit = is_kit_url(url) or is_kit_by_name(name)
            if kit and not p.is_kit:
                p.is_kit = True
                stats["kit_flagged"] += 1

            # 2. Quarantine error pages
            if "desculpe" in name.lower():
                p.verification_status = "quarantined"
                stats["error_quarantined"] += 1
                continue

            # 3. Reclassify type (always re-run to pick up new rules)
            new_type = normalize_product_type(name)
            if kit and not new_type:
                new_type = "kit"
            if new_type and new_type != p.product_type_normalized:
                p.product_type_normalized = new_type
                stats["type_updated"] += 1

            # 4. Reclassify category
            new_cat = normalize_category(p.product_type_normalized, name)
            if kit and not new_cat:
                new_cat = "kit"
            if new_cat and new_cat != p.product_category:
                p.product_category = new_cat
                stats["category_updated"] += 1

            if not p.product_type_normalized:
                stats["still_no_type"] += 1
                print(f"  [NO TYPE] {name[:80]}")

        session.commit()

        print("\n=== Results ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")

        # Final summary
        from sqlalchemy import func
        print("\n=== Final Distribution ===")
        print("\nBy type (all):")
        rows = session.query(ProductORM.product_type_normalized, func.count()).filter(
            ProductORM.brand_slug == BRAND
        ).group_by(ProductORM.product_type_normalized).order_by(func.count().desc()).all()
        for t, ct in rows:
            print(f"  {t}: {ct}")

        print("\nBy category (all):")
        rows = session.query(ProductORM.product_category, func.count()).filter(
            ProductORM.brand_slug == BRAND
        ).group_by(ProductORM.product_category).order_by(func.count().desc()).all()
        for c, ct in rows:
            print(f"  {c}: {ct}")

        print("\nBy type (individual only, is_kit=False):")
        rows = session.query(ProductORM.product_type_normalized, func.count()).filter(
            ProductORM.brand_slug == BRAND, ProductORM.is_kit == False
        ).group_by(ProductORM.product_type_normalized).order_by(func.count().desc()).all()
        for t, ct in rows:
            print(f"  {t}: {ct}")

        total_kits = session.query(ProductORM).filter(
            ProductORM.brand_slug == BRAND, ProductORM.is_kit == True
        ).count()
        total_ind = session.query(ProductORM).filter(
            ProductORM.brand_slug == BRAND, ProductORM.is_kit == False
        ).count()
        print(f"\nKits: {total_kits} | Individuais: {total_ind}")


if __name__ == "__main__":
    main()
