# src/api/routes/brands.py
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.api.dependencies import get_brand_db_from_path, get_router, is_multi_db
from src.storage.database import get_engine
from src.storage.repository import ProductRepository

logger = logging.getLogger("haira.api.brands")

router = APIRouter(tags=["brands"])


def _get_session():
    from sqlalchemy.orm import Session as SASession
    engine = get_engine()
    with SASession(engine) as session:
        yield session


@router.get("/brands")
def list_brands(session: Session = Depends(_get_session)):
    if is_multi_db():
        # Multi-DB mode: read brand list from central database
        db_router = get_router()
        brands = db_router.list_brands()
        return [
            {
                "brand_slug": b.brand_slug,
                "brand_name": b.brand_name,
                "product_count": b.product_count,
                "inci_rate": b.inci_rate,
                "platform": b.platform,
                "is_active": b.is_active,
                "created_at": str(b.created_at) if b.created_at else None,
                "updated_at": str(b.updated_at) if b.updated_at else None,
            }
            for b in brands
        ]

    # Single-DB fallback: existing behaviour
    repo = ProductRepository(session)
    coverages = repo.get_all_brand_coverages()
    return [
        {
            "brand_slug": c.brand_slug,
            "discovered_total": c.discovered_total,
            "hair_total": c.hair_total,
            "extracted_total": c.extracted_total,
            "verified_inci_total": c.verified_inci_total,
            "verified_inci_rate": c.verified_inci_rate,
            "catalog_only_total": c.catalog_only_total,
            "quarantined_total": c.quarantined_total,
            "status": c.status,
            "last_run": str(c.last_run) if c.last_run else None,
        }
        for c in coverages
    ]


@router.get("/brands/{slug}/coverage")
def get_brand_coverage(slug: str, session: Session = Depends(_get_session)):
    repo = ProductRepository(session)
    cov = repo.get_brand_coverage(slug)
    if not cov:
        raise HTTPException(status_code=404, detail="Brand coverage not found")
    return {
        "brand_slug": cov.brand_slug,
        "discovered_total": cov.discovered_total,
        "hair_total": cov.hair_total,
        "kits_total": cov.kits_total,
        "non_hair_total": cov.non_hair_total,
        "extracted_total": cov.extracted_total,
        "verified_inci_total": cov.verified_inci_total,
        "verified_inci_rate": cov.verified_inci_rate,
        "catalog_only_total": cov.catalog_only_total,
        "quarantined_total": cov.quarantined_total,
        "status": cov.status,
        "last_run": str(cov.last_run) if cov.last_run else None,
        "blueprint_version": cov.blueprint_version,
        "coverage_report": cov.coverage_report,
    }


@router.get("/brands/{slug}/products")
def list_brand_products(
    request: Request,
    slug: str,
    verified_only: bool = False,
    exclude_kits: bool = True,
    search: str | None = None,
    category: str | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    brand_session: Session = Depends(get_brand_db_from_path),
):
    """List products for a specific brand (multi-DB mode)."""
    from src.api.routes.products import _serialize_product_list_item

    repo = ProductRepository(brand_session)
    products = repo.get_products(
        brand_slug=slug,
        verified_only=verified_only,
        search=search,
        category=category,
        exclude_kits=exclude_kits,
        limit=limit,
        offset=offset,
    )
    total = repo.count_products(
        brand_slug=slug,
        verified_only=verified_only,
        search=search,
        category=category,
        exclude_kits=exclude_kits,
    )
    items = [_serialize_product_list_item(p) for p in products]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/brands/{slug}/products/{product_id}")
def get_brand_product(
    request: Request,
    slug: str,
    product_id: str,
    brand_session: Session = Depends(get_brand_db_from_path),
):
    """Get product detail within a brand context (multi-DB mode)."""
    from src.api.routes.products import _serialize_product_detail

    repo = ProductRepository(brand_session)
    product = repo.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _serialize_product_detail(product)
