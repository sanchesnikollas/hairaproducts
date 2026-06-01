"""Admin endpoints to maintain denormalised brand counters.

- POST /api/admin/brands/sync-counters         resync every brand
- POST /api/admin/brands/sync-counters/{slug}  resync a single brand

In multi-DB mode (CENTRAL_DATABASE_URL set) this syncs `BrandDatabaseORM` in
the central registry from each brand's DB. In single-DB mode this syncs
`BrandCoverageORM` in the same DB from the live product table. Both modes
cover the same divergence: the list view reads denormalised counters that the
pipeline does not update, so reviewers see "tabela 27, link 112" mismatches
until this runs.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.auth import require_admin
from src.api.dependencies import get_router, is_multi_db
from src.storage.central_sync import (
    sync_all_brands,
    sync_all_coverage,
    sync_brand_counters,
    sync_brand_coverage,
)
from src.storage.database import get_engine

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


def _open_single_db_session() -> Session:
    return Session(get_engine())


@router.post("/sync-counters")
def sync_counters(admin: dict = Depends(require_admin)):
    """Resync denormalised counters for every brand."""
    if is_multi_db():
        results = sync_all_brands(get_router())
    else:
        with _open_single_db_session() as session:
            results = sync_all_coverage(session)
    payload = [_serialize(r) for r in results]
    summary = {
        "mode": "multi-db" if is_multi_db() else "single-db",
        "total": len(payload),
        "updated": sum(1 for r in results if r.changed and not r.error),
        "failed": sum(1 for r in results if r.error),
    }
    logger.info("sync_counters by %s: %s", admin.get("email", "?"), summary)
    return {"summary": summary, "results": payload}


@router.post("/sync-counters/{brand_slug}")
def sync_one(brand_slug: str, admin: dict = Depends(require_admin)):
    """Resync counters for a single brand."""
    if is_multi_db():
        result = sync_brand_counters(get_router(), brand_slug)
    else:
        with _open_single_db_session() as session:
            result = sync_brand_coverage(session, brand_slug)
    if result.error == "brand not registered in central":
        raise HTTPException(status_code=404, detail=result.error)
    return _serialize(result)
