# src/api/routes/products.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.storage.database import get_engine
from src.storage.orm_models import Base, ProductORM, ProductEvidenceORM
from src.storage.repository import ProductRepository

router = APIRouter(tags=["products"])


def _get_session():
    from sqlalchemy.orm import Session as SASession
    from src.storage.database import get_engine
    engine = get_engine()
    with SASession(engine) as session:
        yield session


@router.get("/products")
def list_products(
    brand_slug: str | None = None,
    verified_only: bool = True,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(_get_session),
):
    repo = ProductRepository(session)
    products = repo.get_products(
        brand_slug=brand_slug,
        verified_only=verified_only,
        limit=limit,
        offset=offset,
    )
    return [
        {
            "id": p.id,
            "brand_slug": p.brand_slug,
            "product_name": p.product_name,
            "product_url": p.product_url,
            "image_url_main": p.image_url_main,
            "verification_status": p.verification_status,
            "product_type_normalized": p.product_type_normalized,
            "gender_target": p.gender_target,
            "inci_ingredients": p.inci_ingredients,
            "confidence": p.confidence,
            "product_labels": p.product_labels,
        }
        for p in products
    ]


@router.get("/products/{product_id}")
def get_product(product_id: str, session: Session = Depends(_get_session)):
    repo = ProductRepository(session)
    product = repo.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "id": product.id,
        "brand_slug": product.brand_slug,
        "product_name": product.product_name,
        "product_url": product.product_url,
        "image_url_main": product.image_url_main,
        "image_urls_gallery": product.image_urls_gallery,
        "verification_status": product.verification_status,
        "product_type_raw": product.product_type_raw,
        "product_type_normalized": product.product_type_normalized,
        "gender_target": product.gender_target,
        "hair_relevance_reason": product.hair_relevance_reason,
        "inci_ingredients": product.inci_ingredients,
        "description": product.description,
        "usage_instructions": product.usage_instructions,
        "benefits_claims": product.benefits_claims,
        "size_volume": product.size_volume,
        "price": product.price,
        "currency": product.currency,
        "line_collection": product.line_collection,
        "confidence": product.confidence,
        "extraction_method": product.extraction_method,
        "created_at": str(product.created_at) if product.created_at else None,
        "updated_at": str(product.updated_at) if product.updated_at else None,
        "evidence": [
            {
                "id": e.id,
                "field_name": e.field_name,
                "source_url": e.source_url,
                "evidence_locator": e.evidence_locator,
                "raw_source_text": e.raw_source_text,
                "extraction_method": e.extraction_method,
                "extracted_at": str(e.extracted_at) if e.extracted_at else None,
            }
            for e in product.evidence
        ],
    }
