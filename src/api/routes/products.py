# src/api/routes/products.py
from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.field_validator import validate_product_fields
from src.storage.database import get_engine
from src.storage.orm_models import Base, ProductORM, ProductEvidenceORM
from src.storage.repository import ProductRepository


def _is_kit(p: ProductORM) -> bool:
    """Detect if a product is a kit/combo."""
    name = (p.product_name or "").lower()
    url = (p.product_url or "").lower()
    return (
        "kit " in name or name.startswith("kit ")
        or "/kit-" in url or "/kit/" in url
        or "combo " in name or name.startswith("combo ")
    )


def _validate_product(p: ProductORM) -> dict:
    """Run field cross-validation on a product and return the report dict."""
    report = validate_product_fields(
        product_name=p.product_name,
        inci_ingredients=p.inci_ingredients,
        description=p.description,
        usage_instructions=p.usage_instructions,
        benefits_claims=p.benefits_claims,
        price=p.price,
        currency=p.currency,
        image_url_main=p.image_url_main,
        product_type_normalized=p.product_type_normalized,
    )
    return report.to_dict()

router = APIRouter(tags=["products"])


class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    description: Optional[str] = None
    usage_instructions: Optional[str] = None
    inci_ingredients: Optional[list[str]] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    size_volume: Optional[str] = None
    gender_target: Optional[str] = None
    product_type_normalized: Optional[str] = None
    line_collection: Optional[str] = None
    image_url_main: Optional[str] = None
    benefits_claims: Optional[list[str]] = None
    verification_status: Optional[str] = None
    product_labels: Optional[dict] = None

# If FOCUS_BRAND is set, default brand_slug filter to that brand
_FOCUS_BRAND = os.environ.get("FOCUS_BRAND", "").strip() or None


def _get_session():
    from sqlalchemy.orm import Session as SASession
    from src.storage.database import get_engine
    engine = get_engine()
    with SASession(engine) as session:
        yield session


@router.get("/config/focus-brand")
def get_focus_brand():
    """Return the current focus brand (if set via FOCUS_BRAND env var)."""
    return {"focus_brand": _FOCUS_BRAND}


def _serialize_product_list_item(p: ProductORM) -> dict:
    kit = _is_kit(p)
    return {
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
        "description": p.description,
        "usage_instructions": p.usage_instructions,
        "benefits_claims": p.benefits_claims,
        "product_labels": p.product_labels,
        "price": p.price,
        "is_kit": kit,
        "quality": _validate_product(p),
    }


@router.get("/products")
def list_products(
    brand_slug: str | None = None,
    verified_only: bool = False,
    exclude_kits: bool = True,
    search: str | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(_get_session),
):
    # Apply focus brand default if no brand filter specified
    effective_brand = brand_slug if brand_slug is not None else _FOCUS_BRAND
    repo = ProductRepository(session)
    products = repo.get_products(
        brand_slug=effective_brand,
        verified_only=verified_only,
        search=search,
        limit=limit,
        offset=offset,
    )
    total = repo.count_products(
        brand_slug=effective_brand,
        verified_only=verified_only,
        search=search,
    )
    items = []
    for p in products:
        if exclude_kits and _is_kit(p):
            continue
        items.append(_serialize_product_list_item(p))
    return {"items": items, "total": total, "limit": limit, "offset": offset}


_EXPORT_COLUMNS = [
    "id", "brand_slug", "product_name", "product_url", "image_url_main",
    "verification_status", "product_type_normalized", "gender_target",
    "inci_ingredients", "description", "usage_instructions", "benefits_claims",
    "size_volume", "price", "currency", "line_collection", "confidence",
    "extraction_method", "product_labels",
]


@router.get("/products/export")
def export_products(
    brand_slug: str | None = None,
    verified_only: bool = False,
    search: str | None = None,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    session: Session = Depends(_get_session),
):
    effective_brand = brand_slug if brand_slug is not None else _FOCUS_BRAND
    repo = ProductRepository(session)
    products = repo.get_products(
        brand_slug=effective_brand,
        verified_only=verified_only,
        search=search,
        limit=10000,
        offset=0,
    )

    if format == "json":
        items = [_serialize_product_list_item(p) for p in products]
        return items

    # CSV export
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for p in products:
        row = {}
        for col in _EXPORT_COLUMNS:
            val = getattr(p, col, None)
            if isinstance(val, (list, dict)):
                import json
                val = json.dumps(val, ensure_ascii=False)
            row[col] = val
        writer.writerow(row)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )


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
        "product_labels": product.product_labels,
        "extraction_method": product.extraction_method,
        "created_at": str(product.created_at) if product.created_at else None,
        "updated_at": str(product.updated_at) if product.updated_at else None,
        "quality": _validate_product(product),
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


@router.patch("/products/{product_id}")
def update_product(product_id: str, body: ProductUpdate, session: Session = Depends(_get_session)):
    product = session.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if hasattr(product, field):
            setattr(product, field, value)
    product.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(product)

    return {
        "id": product.id,
        "brand_slug": product.brand_slug,
        "product_name": product.product_name,
        "product_url": product.product_url,
        "image_url_main": product.image_url_main,
        "verification_status": product.verification_status,
        "product_type_normalized": product.product_type_normalized,
        "gender_target": product.gender_target,
        "inci_ingredients": product.inci_ingredients,
        "description": product.description,
        "usage_instructions": product.usage_instructions,
        "benefits_claims": product.benefits_claims,
        "size_volume": product.size_volume,
        "price": product.price,
        "currency": product.currency,
        "line_collection": product.line_collection,
        "confidence": product.confidence,
        "product_labels": product.product_labels,
        "extraction_method": product.extraction_method,
        "updated_at": str(product.updated_at) if product.updated_at else None,
    }
