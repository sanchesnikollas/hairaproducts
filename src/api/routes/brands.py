# src/api/routes/brands.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.storage.database import get_engine
from src.storage.repository import ProductRepository

router = APIRouter(tags=["brands"])


def _get_session():
    from sqlalchemy.orm import Session as SASession
    engine = get_engine()
    with SASession(engine) as session:
        yield session


@router.get("/brands")
def list_brands(session: Session = Depends(_get_session)):
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
