# src/api/routes/brands.py
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from sqlalchemy import func, case, text
from sqlalchemy.orm import Session as SASession

from src.api.dependencies import get_brand_db_from_path, get_router, is_multi_db
from src.storage.database import get_engine
from src.storage.orm_models import ProductORM, ProductIngredientORM
from src.storage.repository import ProductRepository

logger = logging.getLogger("haira.api.brands")

router = APIRouter(tags=["brands"])


def _get_session():
    from src.api.dependencies import is_multi_db
    if is_multi_db():
        # In multi-DB mode, brand list comes from central DB; no default session needed
        yield None
    else:
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

    # Compute quality metrics per brand
    quality = _compute_brand_quality_metrics(session)

    # Build results from coverage records
    coverage_slugs = set()
    results = []
    for c in coverages:
        coverage_slugs.add(c.brand_slug)
        results.append({
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
            "quality": quality.get(c.brand_slug, {}),
        })

    # Add brands that exist in products but have no coverage record
    from sqlalchemy import func, case
    from src.storage.orm_models import ProductORM
    product_brands = (
        session.query(
            ProductORM.brand_slug,
            func.count(ProductORM.id).label("total"),
            func.sum(case((ProductORM.verification_status == "verified_inci", 1), else_=0)).label("verified"),
            func.sum(case((ProductORM.verification_status == "catalog_only", 1), else_=0)).label("catalog"),
            func.sum(case((ProductORM.verification_status == "quarantined", 1), else_=0)).label("quarantined"),
        )
        .group_by(ProductORM.brand_slug)
        .all()
    )
    for row in product_brands:
        if row.brand_slug not in coverage_slugs:
            total = row.total or 0
            verified = row.verified or 0
            rate = round(verified / total, 4) if total > 0 else 0.0
            results.append({
                "brand_slug": row.brand_slug,
                "discovered_total": total,
                "hair_total": 0,
                "extracted_total": total,
                "verified_inci_total": verified,
                "verified_inci_rate": rate,
                "catalog_only_total": row.catalog or 0,
                "quarantined_total": row.quarantined or 0,
                "status": "discovered",
                "last_run": None,
                "quality": quality.get(row.brand_slug, {}),
            })

    # Add registered brands from brands.json — ONLY "marcas principais" (priority <= 1)
    # or brands that have been actively configured (have blueprints)
    import json
    from pathlib import Path
    known_slugs = {r["brand_slug"] for r in results}
    brands_json = Path("config/brands.json")
    if brands_json.exists():
        try:
            registered = json.loads(brands_json.read_text())
            for b in registered:
                slug = b.get("brand_slug", "")
                priority = b.get("priority", 99)
                if slug and slug not in known_slugs and priority is not None:
                    results.append({
                        "brand_slug": slug,
                        "discovered_total": 0,
                        "hair_total": 0,
                        "extracted_total": 0,
                        "verified_inci_total": 0,
                        "verified_inci_rate": 0.0,
                        "catalog_only_total": 0,
                        "quarantined_total": 0,
                        "status": b.get("status", "registered"),
                        "last_run": None,
                        "quality": {},
                    })
        except Exception:
            pass  # brands.json malformed, skip

    return results


def _compute_brand_quality_metrics(session: SASession) -> dict:
    """Compute data quality metrics per brand in one pass."""
    # Count products with key fields filled, avg confidence, avg ingredient count
    rows = session.query(
        ProductORM.brand_slug,
        func.count(ProductORM.id).label("total"),
        func.avg(ProductORM.confidence).label("avg_confidence"),
        func.sum(case((ProductORM.description.isnot(None), 1), else_=0)).label("has_description"),
        func.sum(case((ProductORM.image_url_main.isnot(None), 1), else_=0)).label("has_image"),
        func.sum(case((ProductORM.product_category.isnot(None), 1), else_=0)).label("has_category"),
        func.sum(case((ProductORM.product_labels.isnot(None), 1), else_=0)).label("has_labels"),
    ).group_by(ProductORM.brand_slug).all()

    # Average ingredients per product per brand
    ing_per_product = session.query(
        ProductORM.brand_slug,
        ProductORM.id,
        func.count(ProductIngredientORM.id).label("ing_count"),
    ).join(ProductIngredientORM, ProductIngredientORM.product_id == ProductORM.id).group_by(
        ProductORM.brand_slug, ProductORM.id
    ).subquery()

    ing_avg = session.query(
        ing_per_product.c.brand_slug,
        func.avg(ing_per_product.c.ing_count).label("avg_ingredients"),
    ).group_by(ing_per_product.c.brand_slug).all()
    ing_map = {r.brand_slug: round(float(r.avg_ingredients or 0), 1) for r in ing_avg}

    result = {}
    for r in rows:
        total = r.total or 1
        result[r.brand_slug] = {
            "avg_confidence": round(float(r.avg_confidence or 0) * 100, 1),
            "has_description_pct": round((r.has_description or 0) / total * 100, 1),
            "has_image_pct": round((r.has_image or 0) / total * 100, 1),
            "has_category_pct": round((r.has_category or 0) / total * 100, 1),
            "has_labels_pct": round((r.has_labels or 0) / total * 100, 1),
            "avg_ingredients": ing_map.get(r.brand_slug, 0),
        }
    return result


@router.get("/brands/{slug}/coverage")
def get_brand_coverage(
    request: Request,
    slug: str,
    brand_session: Session = Depends(get_brand_db_from_path),
):
    repo = ProductRepository(brand_session)
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
