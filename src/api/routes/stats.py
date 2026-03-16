# src/api/routes/stats.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.dependencies import get_central_db, get_router, is_multi_db
from src.storage.central_models import BrandDatabaseORM

router = APIRouter(tags=["stats"])


def _get_single_db_session():
    from sqlalchemy.orm import Session as SASession
    from src.storage.database import get_engine
    engine = get_engine()
    with SASession(engine) as session:
        yield session


@router.get("/stats")
def get_stats():
    """Aggregate statistics across all brands."""
    if is_multi_db():
        db_router = get_router()
        session = db_router.get_central_session()
        try:
            row = session.query(
                func.sum(BrandDatabaseORM.product_count).label("total_products"),
                func.avg(BrandDatabaseORM.inci_rate).label("avg_inci_rate"),
                func.count(BrandDatabaseORM.id).label("total_brands"),
            ).filter(BrandDatabaseORM.is_active.is_(True)).one()

            return {
                "total_products": row.total_products or 0,
                "avg_inci_rate": round(float(row.avg_inci_rate or 0), 4),
                "total_brands": row.total_brands or 0,
                "mode": "multi-database",
            }
        finally:
            session.close()
    else:
        # Single-DB fallback: query product and brand counts from existing tables
        from src.storage.database import get_engine
        from src.storage.orm_models import ProductORM, BrandCoverageORM
        from sqlalchemy.orm import Session as SASession

        engine = get_engine()
        with SASession(engine) as session:
            total_products = session.query(func.count(ProductORM.id)).scalar() or 0
            brand_rows = session.query(BrandCoverageORM).all()
            total_brands = len(brand_rows)
            avg_inci = 0.0
            if brand_rows:
                rates = [b.verified_inci_rate for b in brand_rows if b.verified_inci_rate is not None]
                avg_inci = sum(rates) / len(rates) if rates else 0.0

            return {
                "total_products": total_products,
                "avg_inci_rate": round(avg_inci, 4),
                "total_brands": total_brands,
                "mode": "single-database",
            }
