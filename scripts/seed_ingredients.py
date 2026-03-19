"""
Seed the ingredients table from existing inci_ingredients JSON data.
Usage: python3 scripts/seed_ingredients.py [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.database import get_session
from src.storage.orm_models import ProductORM, IngredientORM, ProductIngredientORM
from src.storage.normalized_writer import NormalizedWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed ingredients and product_ingredients tables from existing inci_ingredients JSON data."
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only — no writes to DB")
    args = parser.parse_args()

    session = get_session()

    products = session.query(ProductORM).filter(ProductORM.inci_ingredients.isnot(None)).all()
    logger.info(f"Found {len(products)} products with INCI data")

    raw_names: Counter[str] = Counter()
    for p in products:
        if isinstance(p.inci_ingredients, list):
            for name in p.inci_ingredients:
                if isinstance(name, str) and name.strip():
                    raw_names[name.strip()] += 1

    logger.info(f"Found {len(raw_names)} unique raw ingredient names")

    if args.dry_run:
        logger.info("Dry-run mode — top 20 ingredients by frequency:")
        for name, count in raw_names.most_common(20):
            print(f"  {count:4d}x  {name}")
        if len(raw_names) > 20:
            print(f"  ... and {len(raw_names) - 20} more")
        return

    writer = NormalizedWriter(session)
    created = 0
    for name in raw_names:
        writer.resolve_or_create_ingredient(name)
        created += 1

    session.commit()

    total_ingredients = session.query(IngredientORM).count()
    logger.info(f"Seeded {total_ingredients} canonical ingredients from {created} raw names")

    written = 0
    for p in products:
        count = writer.write_product_ingredients(p)
        written += count

    session.commit()

    total_links = session.query(ProductIngredientORM).count()
    logger.info(f"Created {written} product_ingredient rows across {len(products)} products")
    logger.info(f"Total product_ingredient links in DB: {total_links}")


if __name__ == "__main__":
    main()
