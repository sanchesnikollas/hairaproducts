# src/storage/repository.py
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.core.models import ProductExtraction, QAResult, QAStatus
from src.storage.orm_models import ProductORM, ProductEvidenceORM, QuarantineDetailORM, BrandCoverageORM


class ProductRepository:
    def __init__(self, session: Session):
        self._session = session

    def upsert_product(self, extraction: ProductExtraction, qa: QAResult) -> str:
        existing = (
            self._session.query(ProductORM)
            .filter(ProductORM.product_url == extraction.product_url)
            .first()
        )
        if existing:
            existing.product_name = extraction.product_name
            existing.image_url_main = extraction.image_url_main
            existing.image_urls_gallery = extraction.image_urls_gallery or None
            existing.verification_status = qa.status.value
            existing.product_type_raw = extraction.product_type_raw
            existing.product_type_normalized = extraction.product_type_normalized
            existing.product_category = extraction.product_category
            existing.gender_target = extraction.gender_target.value
            existing.hair_relevance_reason = extraction.hair_relevance_reason
            existing.inci_ingredients = extraction.inci_ingredients
            existing.description = extraction.description
            existing.usage_instructions = extraction.usage_instructions
            existing.benefits_claims = extraction.benefits_claims
            existing.size_volume = extraction.size_volume
            existing.price = extraction.price
            existing.currency = extraction.currency
            existing.line_collection = extraction.line_collection
            existing.variants = extraction.variants
            existing.confidence = extraction.confidence
            existing.extraction_method = extraction.extraction_method
            existing.extracted_at = extraction.extracted_at
            existing.updated_at = datetime.now(timezone.utc)
            product_id = existing.id
        else:
            product = ProductORM(
                brand_slug=extraction.brand_slug,
                product_name=extraction.product_name,
                product_url=extraction.product_url,
                image_url_main=extraction.image_url_main,
                image_urls_gallery=extraction.image_urls_gallery or None,
                verification_status=qa.status.value,
                product_type_raw=extraction.product_type_raw,
                product_type_normalized=extraction.product_type_normalized,
                product_category=extraction.product_category,
                gender_target=extraction.gender_target.value,
                hair_relevance_reason=extraction.hair_relevance_reason,
                inci_ingredients=extraction.inci_ingredients,
                description=extraction.description,
                usage_instructions=extraction.usage_instructions,
                benefits_claims=extraction.benefits_claims,
                size_volume=extraction.size_volume,
                price=extraction.price,
                currency=extraction.currency,
                line_collection=extraction.line_collection,
                variants=extraction.variants,
                confidence=extraction.confidence,
                extraction_method=extraction.extraction_method,
                extracted_at=extraction.extracted_at,
            )
            self._session.add(product)
            self._session.flush()
            product_id = product.id

        # Save evidence
        for ev in extraction.evidence:
            evidence_orm = ProductEvidenceORM(
                product_id=product_id,
                field_name=ev.field_name,
                source_url=ev.source_url,
                evidence_locator=ev.evidence_locator,
                raw_source_text=ev.raw_source_text,
                extraction_method=ev.extraction_method.value,
                extracted_at=ev.extracted_at,
            )
            self._session.add(evidence_orm)

        # Save quarantine details
        if qa.status == QAStatus.QUARANTINED and qa.rejection_reason:
            existing_q = (
                self._session.query(QuarantineDetailORM)
                .filter(QuarantineDetailORM.product_id == product_id)
                .first()
            )
            if existing_q:
                existing_q.rejection_reason = qa.rejection_reason
            else:
                qd = QuarantineDetailORM(
                    product_id=product_id,
                    rejection_reason=qa.rejection_reason,
                    rejection_code=qa.checks_failed[0] if qa.checks_failed else None,
                )
                self._session.add(qd)

        return product_id

    def _apply_filters(self, query, brand_slug=None, verified_only=False, search=None, category=None):
        if brand_slug:
            query = query.filter(ProductORM.brand_slug == brand_slug)
        if verified_only:
            query = query.filter(ProductORM.verification_status == "verified_inci")
        if category:
            query = query.filter(ProductORM.product_category == category)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    ProductORM.product_name.ilike(pattern),
                    ProductORM.description.ilike(pattern),
                )
            )
        return query

    def get_products(
        self,
        brand_slug: str | None = None,
        verified_only: bool = False,
        search: str | None = None,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProductORM]:
        query = self._apply_filters(
            self._session.query(ProductORM),
            brand_slug=brand_slug, verified_only=verified_only, search=search, category=category,
        )
        return query.offset(offset).limit(limit).all()

    def count_products(
        self,
        brand_slug: str | None = None,
        verified_only: bool = False,
        search: str | None = None,
        category: str | None = None,
    ) -> int:
        query = self._apply_filters(
            self._session.query(func.count(ProductORM.id)),
            brand_slug=brand_slug, verified_only=verified_only, search=search, category=category,
        )
        return query.scalar()

    def get_products_without_inci(self, brand_slug: str) -> list[ProductORM]:
        """Get catalog_only products without INCI ingredients for a brand."""
        return (
            self._session.query(ProductORM)
            .filter(
                ProductORM.brand_slug == brand_slug,
                ProductORM.verification_status == "catalog_only",
                or_(
                    ProductORM.inci_ingredients.is_(None),
                    ProductORM.inci_ingredients == "[]",
                ),
            )
            .all()
        )

    def get_product_by_id(self, product_id: str) -> ProductORM | None:
        return self._session.query(ProductORM).filter(ProductORM.id == product_id).first()

    def upsert_brand_coverage(self, stats: dict) -> None:
        slug = stats["brand_slug"]
        existing = (
            self._session.query(BrandCoverageORM)
            .filter(BrandCoverageORM.brand_slug == slug)
            .first()
        )
        if existing:
            for key, val in stats.items():
                if key != "brand_slug" and hasattr(existing, key):
                    setattr(existing, key, val)
            existing.last_run = datetime.now(timezone.utc)
        else:
            cov = BrandCoverageORM(**stats)
            cov.last_run = datetime.now(timezone.utc)
            self._session.add(cov)

    def get_brand_coverage(self, brand_slug: str) -> BrandCoverageORM | None:
        return (
            self._session.query(BrandCoverageORM)
            .filter(BrandCoverageORM.brand_slug == brand_slug)
            .first()
        )

    def get_all_brand_coverages(self) -> list[BrandCoverageORM]:
        return self._session.query(BrandCoverageORM).all()

    def update_product_labels(self, product_id: str, labels: dict) -> None:
        """Update the product_labels JSON for a product."""
        product = self.get_product_by_id(product_id)
        if product:
            product.product_labels = labels
            product.updated_at = datetime.now(timezone.utc)
