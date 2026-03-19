# src/storage/normalized_writer.py
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from src.storage.orm_models import (
    ProductORM, IngredientORM, IngredientAliasORM, ProductIngredientORM,
    ProductImageORM, ProductCompositionORM, ClaimORM, ProductClaimORM,
)

logger = logging.getLogger(__name__)


class NormalizedWriter:
    """Writes normalized data from ProductORM into junction/entity tables."""

    def __init__(self, session: Session):
        self._session = session
        self._ingredient_cache: dict[str, IngredientORM] = {}

    def resolve_or_create_ingredient(self, raw_name: str) -> IngredientORM:
        normalized = raw_name.strip()
        cache_key = normalized.lower()

        if cache_key in self._ingredient_cache:
            return self._ingredient_cache[cache_key]

        existing = self._session.query(IngredientORM).filter(
            IngredientORM.canonical_name == normalized
        ).first()
        if existing:
            self._ingredient_cache[cache_key] = existing
            return existing

        alias = self._session.query(IngredientAliasORM).filter(
            IngredientAliasORM.alias == normalized
        ).first()
        if alias:
            ing = self._session.get(IngredientORM, alias.ingredient_id)
            if ing:
                self._ingredient_cache[cache_key] = ing
                return ing

        ing = IngredientORM(canonical_name=normalized)
        self._session.add(ing)
        self._session.flush()
        self._ingredient_cache[cache_key] = ing
        return ing

    def write_product_ingredients(self, product: ProductORM) -> int:
        if not product.inci_ingredients:
            return 0
        ingredients = product.inci_ingredients
        if not isinstance(ingredients, list):
            return 0

        self._session.query(ProductIngredientORM).filter_by(product_id=product.id).delete()

        count = 0
        for i, raw_name in enumerate(ingredients):
            if not isinstance(raw_name, str) or not raw_name.strip():
                continue
            ingredient = self.resolve_or_create_ingredient(raw_name)
            pi = ProductIngredientORM(
                product_id=product.id,
                ingredient_id=ingredient.id,
                position=i + 1,
                raw_name=raw_name.strip(),
                validation_status="raw",
            )
            self._session.add(pi)
            count += 1

        self._session.flush()
        return count

    def write_product_claims(self, product: ProductORM) -> int:
        self._session.query(ProductClaimORM).filter_by(product_id=product.id).delete()

        if not product.product_labels or not isinstance(product.product_labels, dict):
            return 0

        detected = product.product_labels.get("detected", [])
        inferred = product.product_labels.get("inferred", [])
        confidence = product.product_labels.get("confidence", 0.0)

        count = 0
        all_claims = [(c, "keyword") for c in detected] + [(c, "inci_inference") for c in inferred]
        for claim_name, source in all_claims:
            existing = self._session.query(ClaimORM).filter_by(canonical_name=claim_name).first()
            if not existing:
                existing = ClaimORM(
                    canonical_name=claim_name,
                    display_name=claim_name.replace("_", " ").title(),
                    category="seal",
                )
                self._session.add(existing)
                self._session.flush()

            pc = ProductClaimORM(
                product_id=product.id,
                claim_id=existing.id,
                source=source,
                confidence_score=confidence,
            )
            self._session.add(pc)
            count += 1

        self._session.flush()
        return count

    def write_product_images(self, product: ProductORM) -> int:
        self._session.query(ProductImageORM).filter_by(product_id=product.id).delete()

        count = 0
        if product.image_url_main:
            img = ProductImageORM(
                product_id=product.id, url=product.image_url_main,
                image_type="main", position=0,
            )
            self._session.add(img)
            count += 1

        if product.image_urls_gallery and isinstance(product.image_urls_gallery, list):
            for i, url in enumerate(product.image_urls_gallery):
                if isinstance(url, str) and url.strip():
                    img = ProductImageORM(
                        product_id=product.id, url=url.strip(),
                        image_type="gallery", position=i + 1,
                    )
                    self._session.add(img)
                    count += 1

        if count:
            self._session.flush()
        return count

    def write_product_compositions(self, product: ProductORM) -> int:
        self._session.query(ProductCompositionORM).filter_by(product_id=product.id).delete()

        if not product.composition:
            return 0

        comp = ProductCompositionORM(
            product_id=product.id,
            section_label="Composição",
            content=product.composition,
        )
        self._session.add(comp)
        self._session.flush()
        return 1

    def write_all(self, product: ProductORM) -> dict:
        """Write all normalized data. Single commit at end."""
        result = {
            "ingredients": self.write_product_ingredients(product),
            "claims": self.write_product_claims(product),
            "images": self.write_product_images(product),
            "compositions": self.write_product_compositions(product),
        }
        self._session.commit()
        return result
