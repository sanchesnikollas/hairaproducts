"""Admin endpoints for brand registry + counter sync.

Counter sync (já existia):
- POST /api/admin/brands/sync-counters         resync every brand
- POST /api/admin/brands/sync-counters/{slug}  resync a single brand

CRUD do registro de marcas (nova adição):
- GET    /api/admin/brands/registry            lista todas as marcas
- POST   /api/admin/brands/registry            cria nova
- PATCH  /api/admin/brands/registry/{slug}     edita
- DELETE /api/admin/brands/registry/{slug}     remove

Tudo require_admin.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.api.auth import require_admin
from src.api.dependencies import get_ops_session, get_router, is_multi_db
from src.storage.central_sync import (
    sync_all_brands,
    sync_all_coverage,
    sync_brand_counters,
    sync_brand_coverage,
)
from src.storage.database import get_engine
from src.storage.orm_models import BrandRegistryORM, ProductORM

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


# ─────────────────────────────────────────────────────────────────────────────
# CRUD do registry (criação/edição de marcas direto pela UI)
# ─────────────────────────────────────────────────────────────────────────────

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}[a-z0-9]$")
_ALLOWED_STATUS = {"active", "blocked", "blocked_maintenance", "out_of_scope"}
_ALLOWED_COUNTRY = {"Brasil", "Internacional", "Outros"}
_ALLOWED_PLATFORM = {"VTEX", "Shopify", "WooCommenrce", "WooCommerce", "Magento", "Custom"}


def _slugify(name: str) -> str:
    """Slug compatível com brands.json: lower, sem acento, espaços → hifens."""
    import unicodedata
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:80]


class BrandCreate(BaseModel):
    brand_name: str = Field(..., min_length=1, max_length=255)
    brand_slug: str | None = Field(None, max_length=255)
    official_url_root: str | None = Field(None, max_length=2000)
    country: str | None = Field(None, max_length=80)
    priority: int | None = None
    status: str = "active"
    platform: str | None = Field(None, max_length=50)
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in _ALLOWED_STATUS:
            raise ValueError(f"status inválido. Permitidos: {sorted(_ALLOWED_STATUS)}")
        return v

    @field_validator("country")
    @classmethod
    def _check_country(cls, v: str | None) -> str | None:
        if v and v not in _ALLOWED_COUNTRY:
            raise ValueError(f"country inválido. Permitidos: {sorted(_ALLOWED_COUNTRY)}")
        return v


class BrandUpdate(BaseModel):
    brand_name: str | None = Field(None, min_length=1, max_length=255)
    official_url_root: str | None = Field(None, max_length=2000)
    country: str | None = Field(None, max_length=80)
    priority: int | None = None
    status: str | None = None
    platform: str | None = Field(None, max_length=50)
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_STATUS:
            raise ValueError(f"status inválido. Permitidos: {sorted(_ALLOWED_STATUS)}")
        return v


def _serialize_brand(row: BrandRegistryORM) -> dict:
    return {
        "brand_slug": row.brand_slug,
        "brand_name": row.brand_name,
        "official_url_root": row.official_url_root,
        "country": row.country,
        "priority": row.priority,
        "status": row.status,
        "platform": row.platform,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/registry")
def list_brand_registry(
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    """Lista todas as marcas cadastradas (ordenadas por nome)."""
    rows = session.query(BrandRegistryORM).order_by(BrandRegistryORM.brand_name).all()
    return {"brands": [_serialize_brand(r) for r in rows], "total": len(rows)}


@router.post("/registry", status_code=201)
def create_brand(
    body: BrandCreate,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    """Cria nova marca. Slug é gerado do nome se omitido."""
    slug = body.brand_slug or _slugify(body.brand_name)
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=400,
            detail=f"slug inválido '{slug}': use minúsculas, números e hífens, 3-80 chars",
        )
    existing = session.query(BrandRegistryORM).filter(BrandRegistryORM.brand_slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"slug '{slug}' já existe")

    row = BrandRegistryORM(
        brand_slug=slug,
        brand_name=body.brand_name,
        official_url_root=body.official_url_root,
        country=body.country,
        priority=body.priority,
        status=body.status,
        platform=body.platform,
        notes=body.notes,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("brand_registry created %s by %s", slug, admin.get("email", admin.get("sub", "?")))
    return _serialize_brand(row)


@router.patch("/registry/{brand_slug}")
def update_brand(
    brand_slug: str,
    body: BrandUpdate,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    """Edita campos da marca. Não muda o slug (use POST + DELETE pra renomear)."""
    row = session.query(BrandRegistryORM).filter(BrandRegistryORM.brand_slug == brand_slug).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"marca '{brand_slug}' não cadastrada")

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(row)
    logger.info("brand_registry updated %s by %s: %s", brand_slug, admin.get("email", "?"), list(updates.keys()))
    return _serialize_brand(row)


@router.delete("/registry/{brand_slug}", status_code=204)
def delete_brand(
    brand_slug: str,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    """Remove marca do registry. Bloqueia se houver produtos associados (anti-órfão)."""
    row = session.query(BrandRegistryORM).filter(BrandRegistryORM.brand_slug == brand_slug).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"marca '{brand_slug}' não cadastrada")
    product_count = session.query(ProductORM).filter(ProductORM.brand_slug == brand_slug).count()
    if product_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"marca '{brand_slug}' tem {product_count} produtos; remova-os antes",
        )
    session.delete(row)
    session.commit()
    logger.info("brand_registry deleted %s by %s", brand_slug, admin.get("email", "?"))
