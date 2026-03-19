"""Export Amend products to CSV grouped by type/category."""
from __future__ import annotations

import csv
import json

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from src.storage.orm_models import ProductORM

BRAND = "amend"


def main() -> None:
    engine = create_engine("sqlite:///haira.db")
    with Session(engine) as s:
        products = (
            s.query(ProductORM)
            .filter(
                ProductORM.brand_slug == BRAND,
                ProductORM.verification_status != "quarantined",
            )
            .order_by(
                ProductORM.product_category,
                ProductORM.product_type_normalized,
                ProductORM.product_name,
            )
            .all()
        )

        fields = [
            "product_name",
            "product_type_normalized",
            "product_category",
            "is_kit",
            "verification_status",
            "price",
            "size_volume",
            "line_collection",
            "product_url",
            "image_url_main",
            "inci_count",
            "labels_detected",
            "labels_inferred",
            "confidence",
            "description",
        ]

        with open("exports/amend_base_completa.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for p in products:
                labels = json.loads(p.product_labels) if isinstance(p.product_labels, str) else (p.product_labels or {})
                inci = p.inci_ingredients if isinstance(p.inci_ingredients, list) else (
                    json.loads(p.inci_ingredients) if isinstance(p.inci_ingredients, str) and p.inci_ingredients else []
                )
                w.writerow({
                    "product_name": p.product_name,
                    "product_type_normalized": p.product_type_normalized,
                    "product_category": p.product_category,
                    "is_kit": p.is_kit,
                    "verification_status": p.verification_status,
                    "price": p.price,
                    "size_volume": p.size_volume,
                    "line_collection": p.line_collection,
                    "product_url": p.product_url,
                    "image_url_main": p.image_url_main,
                    "inci_count": len(inci),
                    "labels_detected": ", ".join(labels.get("detected", [])),
                    "labels_inferred": ", ".join(labels.get("inferred", [])),
                    "confidence": p.confidence,
                    "description": (p.description or "")[:200],
                })

        print(f"Exportados: {len(products)} produtos (excluindo quarantined)")

        print("\n=== RESUMO FINAL DA BASE AMEND ===")
        print("\nPor categoria:")
        for cat, ct in (
            s.query(ProductORM.product_category, func.count())
            .filter(ProductORM.brand_slug == BRAND, ProductORM.verification_status != "quarantined")
            .group_by(ProductORM.product_category)
            .order_by(func.count().desc())
            .all()
        ):
            kit_ct = (
                s.query(ProductORM)
                .filter(
                    ProductORM.brand_slug == BRAND,
                    ProductORM.product_category == cat,
                    ProductORM.is_kit == True,
                    ProductORM.verification_status != "quarantined",
                )
                .count()
            )
            ind_ct = ct - kit_ct
            print(f"  {cat}: {ct} total ({ind_ct} individuais + {kit_ct} kits)")

        print("\nPor tipo (só individuais):")
        for t, ct in (
            s.query(ProductORM.product_type_normalized, func.count())
            .filter(
                ProductORM.brand_slug == BRAND,
                ProductORM.is_kit == False,
                ProductORM.verification_status != "quarantined",
            )
            .group_by(ProductORM.product_type_normalized)
            .order_by(func.count().desc())
            .all()
        ):
            print(f"  {t}: {ct}")

        total = len(products)
        kits = sum(1 for p in products if p.is_kit)
        ind = total - kits
        print(f"\nTOTAL: {total} | Individuais: {ind} | Kits: {kits}")
        print("Arquivo: exports/amend_base_completa.csv")


if __name__ == "__main__":
    main()
