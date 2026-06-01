# src/storage/central_sync.py
"""Sync denormalised brand counters from the live product table.

Two storage modes need this:

* **Multi-DB** (`CENTRAL_DATABASE_URL` set): `BrandDatabaseORM` in the central
  registry has `product_count`/`inci_rate` columns the pipeline does not update.
  Without a sync, `/api/brands` list view reads frozen migration-era counters
  while `/api/brands/{slug}/coverage` reads live brand DBs and shows current
  values — same brand, two numbers.
* **Single-DB** (`DATABASE_URL` only): `BrandCoverageORM` rows are written by
  the CLI scrape and the migration endpoint, but `haira labels` and incremental
  product uploads do not touch them. `last_run` ends up months stale relative
  to the products it should describe (reviewers reported REDKEN coverage at 54
  while the live products table had 110).

Both paths recompute the canonical count (hair products, excluding non_hair,
including kits) and write it back to the appropriate counter table.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.storage.central_models import BrandDatabaseORM
from src.storage.db_router import DatabaseRouter
from src.storage.orm_models import BrandCoverageORM, ProductORM

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


# ---------------------------------------------------------------------------
# Per-brand canonical counts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Counts:
    total_hair: int
    verified_inci: int
    catalog_only: int
    quarantined: int
    kits: int
    non_hair: int


def _canonical_counts(session: Session, brand_slug: str) -> _Counts:
    """Return granular counts for a brand from the live product table.

    `total_hair` excludes `product_category == 'non_hair'`; kits stay in.
    """
    non_hair_filter = or_(
        ProductORM.product_category != "non_hair",
        ProductORM.product_category.is_(None),
    )
    base_q = session.query(func.count(ProductORM.id)).filter(
        ProductORM.brand_slug == brand_slug
    )

    total_hair = base_q.filter(non_hair_filter).scalar() or 0
    verified = (
        base_q.filter(non_hair_filter, ProductORM.verification_status == "verified_inci")
        .scalar()
        or 0
    )
    catalog = (
        base_q.filter(non_hair_filter, ProductORM.verification_status == "catalog_only")
        .scalar()
        or 0
    )
    quarantined = (
        base_q.filter(non_hair_filter, ProductORM.verification_status == "quarantined")
        .scalar()
        or 0
    )
    kits = base_q.filter(non_hair_filter, ProductORM.is_kit.is_(True)).scalar() or 0
    non_hair = base_q.filter(ProductORM.product_category == "non_hair").scalar() or 0
    return _Counts(
        total_hair=int(total_hair),
        verified_inci=int(verified),
        catalog_only=int(catalog),
        quarantined=int(quarantined),
        kits=int(kits),
        non_hair=int(non_hair),
    )


# ---------------------------------------------------------------------------
# Multi-DB path — central BrandDatabaseORM
# ---------------------------------------------------------------------------


def sync_brand_counters(router: DatabaseRouter, brand_slug: str) -> BrandSyncResult:
    """Sync `BrandDatabaseORM` (central) from the per-brand DB. Multi-DB mode."""
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
                counts = _canonical_counts(brand_session, brand_slug)
        except Exception as exc:  # network, DB down — keep central as-is
            logger.warning("sync %s: brand DB unreachable: %s", brand_slug, exc)
            return BrandSyncResult(
                brand_slug=brand_slug,
                previous_count=prev_count,
                new_count=prev_count,
                previous_rate=prev_rate,
                new_rate=prev_rate,
                error=str(exc),
            )

        new_rate = (
            round(counts.verified_inci / counts.total_hair, 4)
            if counts.total_hair > 0
            else 0.0
        )
        brand.product_count = counts.total_hair
        brand.inci_rate = new_rate
        central.add(brand)
        central.commit()

        return BrandSyncResult(
            brand_slug=brand_slug,
            previous_count=prev_count,
            new_count=counts.total_hair,
            previous_rate=prev_rate,
            new_rate=new_rate,
        )


def sync_all_brands(router: DatabaseRouter) -> list[BrandSyncResult]:
    """Sync every active brand registered in central."""
    with router.get_central_session() as central:
        active = (
            central.query(BrandDatabaseORM.brand_slug)
            .filter(BrandDatabaseORM.is_active.is_(True))
            .all()
        )
    return [sync_brand_counters(router, row[0]) for row in active]


# ---------------------------------------------------------------------------
# Single-DB path — BrandCoverageORM in the same DB as products
# ---------------------------------------------------------------------------


def sync_brand_coverage(session: Session, brand_slug: str) -> BrandSyncResult:
    """Update or create `BrandCoverageORM` for one brand from live products.

    Safe in single-DB mode. Does not change `discovered_total`, `last_run`, or
    `coverage_report` (those describe the last full scrape run, not the
    current product count). `extracted_total`/`verified_inci_total`/
    `catalog_only_total`/`quarantined_total`/`kits_total`/`hair_total`/
    `non_hair_total`/`verified_inci_rate` are recomputed.
    """
    counts = _canonical_counts(session, brand_slug)
    coverage = (
        session.query(BrandCoverageORM)
        .filter(BrandCoverageORM.brand_slug == brand_slug)
        .first()
    )
    prev_count = int(coverage.extracted_total) if coverage else 0
    prev_rate = float(coverage.verified_inci_rate) if coverage else 0.0
    rate = (
        round(counts.verified_inci / counts.total_hair, 4)
        if counts.total_hair > 0
        else 0.0
    )

    if coverage is None:
        coverage = BrandCoverageORM(brand_slug=brand_slug, status="synced")
        session.add(coverage)

    coverage.hair_total = counts.total_hair
    coverage.kits_total = counts.kits
    coverage.non_hair_total = counts.non_hair
    coverage.extracted_total = counts.total_hair
    coverage.verified_inci_total = counts.verified_inci
    coverage.verified_inci_rate = rate
    coverage.catalog_only_total = counts.catalog_only
    coverage.quarantined_total = counts.quarantined
    # Bump last_run so reviewers know the row is fresh — but only when the
    # numbers actually changed, so audit history is preserved otherwise.
    if prev_count != counts.total_hair or abs(prev_rate - rate) > 1e-4:
        coverage.last_run = datetime.now(timezone.utc)
    session.commit()

    return BrandSyncResult(
        brand_slug=brand_slug,
        previous_count=prev_count,
        new_count=counts.total_hair,
        previous_rate=prev_rate,
        new_rate=rate,
    )


def sync_all_coverage(session: Session) -> list[BrandSyncResult]:
    """Sync coverage for every brand that has products in the DB."""
    brand_slugs = [
        row[0]
        for row in session.query(ProductORM.brand_slug).distinct().all()
        if row[0]
    ]
    return [sync_brand_coverage(session, slug) for slug in brand_slugs]
