# src/storage/central_sync.py
"""Sync denormalized counters in the central brand registry from each brand DB.

`BrandDatabaseORM.product_count` and `inci_rate` are denormalized fields that the
pipeline (scrape/labels) does NOT update. They were only seeded once by the
initial migration scripts. Without this sync, `/api/brands` (which reads these
columns for the list view) shows stale numbers while `/api/brands/{slug}` reads
the live brand DB and shows the correct numbers — that's the "tabela 243, link
247" divergence the reviewers reported.

Canonical count (matches what users expect on the brand card):
    total       = hair products (excludes non_hair, includes kits)
    verified    = total filtered by verification_status == 'verified_inci'
    inci_rate   = verified / total
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.storage.central_models import BrandDatabaseORM
from src.storage.db_router import DatabaseRouter
from src.storage.orm_models import ProductORM

logger = logging.getLogger("haira.central_sync")


@dataclass(frozen=True)
class BrandSyncResult:
    brand_slug: str
    previous_count: int
    new_count: int
    previous_rate: float
    new_rate: float
    error: str | None = None

    @property
    def changed(self) -> bool:
        return (
            self.previous_count != self.new_count
            or abs(self.previous_rate - self.new_rate) > 1e-4
        )


def _canonical_counts(session: Session, brand_slug: str) -> tuple[int, int]:
    """Return (total_hair, verified_inci) for the brand.

    `non_hair` products are excluded (matches default UI behaviour); kits are
    kept (they are real products customers buy).
    """
    base_filter = (
        or_(
            ProductORM.product_category != "non_hair",
            ProductORM.product_category.is_(None),
        ),
        ProductORM.brand_slug == brand_slug,
    )
    total = session.query(func.count(ProductORM.id)).filter(*base_filter).scalar() or 0
    verified = (
        session.query(func.count(ProductORM.id))
        .filter(*base_filter, ProductORM.verification_status == "verified_inci")
        .scalar()
        or 0
    )
    return int(total), int(verified)


def sync_brand_counters(router: DatabaseRouter, brand_slug: str) -> BrandSyncResult:
    """Sync counters for a single brand. Safe to call after a scrape finishes."""
    with router.get_central_session() as central:
        brand = (
            central.query(BrandDatabaseORM)
            .filter(BrandDatabaseORM.brand_slug == brand_slug)
            .first()
        )
        if brand is None:
            return BrandSyncResult(
                brand_slug=brand_slug,
                previous_count=0,
                new_count=0,
                previous_rate=0.0,
                new_rate=0.0,
                error="brand not registered in central",
            )
        prev_count = int(brand.product_count or 0)
        prev_rate = float(brand.inci_rate or 0.0)

        try:
            with router.get_session(brand_slug) as brand_session:
                total, verified = _canonical_counts(brand_session, brand_slug)
        except Exception as exc:  # network, DB down, etc — keep central as-is
            logger.warning("sync %s: brand DB unreachable: %s", brand_slug, exc)
            return BrandSyncResult(
                brand_slug=brand_slug,
                previous_count=prev_count,
                new_count=prev_count,
                previous_rate=prev_rate,
                new_rate=prev_rate,
                error=str(exc),
            )

        new_rate = round(verified / total, 4) if total > 0 else 0.0
        brand.product_count = total
        brand.inci_rate = new_rate
        central.add(brand)
        central.commit()

        result = BrandSyncResult(
            brand_slug=brand_slug,
            previous_count=prev_count,
            new_count=total,
            previous_rate=prev_rate,
            new_rate=new_rate,
        )
        if result.changed:
            logger.info(
                "sync %s: count %d -> %d, rate %.2f%% -> %.2f%%",
                brand_slug,
                prev_count,
                total,
                prev_rate * 100,
                new_rate * 100,
            )
        return result


def sync_all_brands(router: DatabaseRouter) -> list[BrandSyncResult]:
    """Sync counters for every active brand in central. Returns per-brand results."""
    results: list[BrandSyncResult] = []
    with router.get_central_session() as central:
        active = (
            central.query(BrandDatabaseORM.brand_slug)
            .filter(BrandDatabaseORM.is_active.is_(True))
            .all()
        )
        slugs = [row[0] for row in active]

    for slug in slugs:
        results.append(sync_brand_counters(router, slug))
    return results
