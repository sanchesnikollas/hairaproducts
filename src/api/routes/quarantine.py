# src/api/routes/quarantine.py
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.storage.database import get_engine
from src.storage.orm_models import ProductORM, QuarantineDetailORM

router = APIRouter(tags=["quarantine"])


def _get_session():
    from sqlalchemy.orm import Session as SASession
    engine = get_engine()
    with SASession(engine) as session:
        yield session


@router.get("/quarantine")
def list_quarantined(
    brand_slug: str | None = None,
    review_status: str = "pending",
    session: Session = Depends(_get_session),
):
    query = (
        session.query(QuarantineDetailORM)
        .join(ProductORM)
        .filter(QuarantineDetailORM.review_status == review_status)
    )
    if brand_slug:
        query = query.filter(ProductORM.brand_slug == brand_slug)
    items = query.limit(100).all()
    return [
        {
            "id": q.id,
            "product_id": q.product_id,
            "product_name": q.product.product_name if q.product else None,
            "product_url": q.product.product_url if q.product else None,
            "brand_slug": q.product.brand_slug if q.product else None,
            "rejection_reason": q.rejection_reason,
            "rejection_code": q.rejection_code,
            "review_status": q.review_status,
            "reviewer_notes": q.reviewer_notes,
        }
        for q in items
    ]


@router.post("/quarantine/{quarantine_id}/approve")
def approve_quarantined(
    quarantine_id: str,
    notes: str = "",
    session: Session = Depends(_get_session),
):
    detail = session.query(QuarantineDetailORM).filter(QuarantineDetailORM.id == quarantine_id).first()
    if not detail:
        raise HTTPException(status_code=404, detail="Quarantine record not found")

    detail.review_status = "approved"
    detail.reviewer_notes = notes
    detail.reviewed_at = datetime.now(timezone.utc)

    # Update the product status to verified_inci
    if detail.product:
        detail.product.verification_status = "verified_inci"

    session.commit()
    return {"status": "approved", "quarantine_id": quarantine_id}
