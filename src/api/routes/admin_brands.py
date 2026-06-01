"""Admin endpoints to maintain the central brand registry.

- POST /api/admin/brands/sync-counters         resync product_count + inci_rate for all brands
- POST /api/admin/brands/sync-counters/{slug}  resync a single brand

These exist because `BrandDatabaseORM.product_count` and `inci_rate` are
denormalised: the pipeline does not update them, so the list endpoint shows
stale numbers until we resync. Run manually whenever the brand cards diverge
from per-brand views.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import require_admin
from src.api.dependencies import get_router
from src.storage.central_sync import sync_all_brands, sync_brand_counters

logger = logging.getLogger("haira.admin_brands")

router = APIRouter(prefix="/admin/brands", tags=["admin"])


def _serialize(r) -> dict:
    return {
        "brand_slug": r.brand_slug,
        "previous_count": r.previous_count,
        "new_count": r.new_count,
        "previous_rate": round(r.previous_rate, 4),
        "new_rate": round(r.new_rate, 4),
        "changed": r.changed,
        "error": r.error,
    }


@router.post("/sync-counters")
def sync_counters(admin: dict = Depends(require_admin)):
    """Resync denormalised counters for every active brand."""
    db_router = get_router()
    results = sync_all_brands(db_router)
    payload = [_serialize(r) for r in results]
    summary = {
        "total": len(payload),
        "updated": sum(1 for r in results if r.changed and not r.error),
        "failed": sum(1 for r in results if r.error),
    }
    logger.info("sync_counters by %s: %s", admin.get("email", "?"), summary)
    return {"summary": summary, "results": payload}


@router.post("/sync-counters/{brand_slug}")
def sync_one(brand_slug: str, admin: dict = Depends(require_admin)):
    """Resync counters for a single brand."""
    db_router = get_router()
    result = sync_brand_counters(db_router, brand_slug)
    if result.error and result.error == "brand not registered in central":
        raise HTTPException(status_code=404, detail=result.error)
    return _serialize(result)
