from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from src.api.auth import get_current_user, require_admin
from src.api.dependencies import get_ops_session
from src.storage.orm_models import ProductORM
from src.storage.ops_models import RevisionHistoryORM
from src.core.revision_service import create_revisions, get_entity_history
from src.core.confidence import calculate_confidence

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user), session: Session = Depends(get_ops_session)):
    from src.storage.orm_models import BrandCoverageORM

    total = session.query(func.count(ProductORM.id)).scalar() or 0
    pending = session.query(func.count(ProductORM.id)).filter(ProductORM.status_editorial == "pendente").scalar() or 0
    quarantined = session.query(func.count(ProductORM.id)).filter(
        ProductORM.verification_status == "quarantined"
    ).scalar() or 0
    published = session.query(func.count(ProductORM.id)).filter(ProductORM.status_publicacao == "publicado").scalar() or 0
    avg_conf = session.query(func.avg(ProductORM.confidence)).scalar() or 0.0

    coverages = session.query(BrandCoverageORM).all()
    if coverages:
        total_verified = sum(c.verified_inci_total or 0 for c in coverages)
        total_extracted = sum(c.extracted_total or 0 for c in coverages)
        inci_coverage = round(total_verified / total_extracted * 100, 1) if total_extracted > 0 else 0.0
    else:
        inci_coverage = 0.0

    low_confidence = (
        session.query(ProductORM)
        .filter(ProductORM.confidence < 50)
        .order_by(ProductORM.confidence.asc())
        .limit(20)
        .all()
    )

    recent_activity = (
        session.query(RevisionHistoryORM)
        .order_by(RevisionHistoryORM.created_at.desc())
        .limit(20)
        .all()
    )

    return {
        "kpis": {
            "total_products": total,
            "inci_coverage": inci_coverage,
            "pending_review": pending,
            "quarantined": quarantined,
            "published": published,
            "avg_confidence": round(float(avg_conf), 1),
        },
        "low_confidence": [
            {"id": p.id, "product_name": p.product_name, "brand_slug": p.brand_slug,
             "confidence": p.confidence, "status_editorial": p.status_editorial}
            for p in low_confidence
        ],
        "recent_activity": [
            {"revision_id": r.revision_id, "entity_type": r.entity_type, "entity_id": r.entity_id,
             "field_name": r.field_name, "changed_by": r.changed_by, "change_source": r.change_source,
             "created_at": str(r.created_at)}
            for r in recent_activity
        ],
    }


class OpsProductUpdate(BaseModel):
    product_name: str | None = None
    description: str | None = None
    usage_instructions: str | None = None
    inci_ingredients: str | None = None
    product_category: str | None = None
    status_editorial: str | None = None
    status_publicacao: str | None = None
    status_operacional: str | None = None


class BatchStatusUpdate(BaseModel):
    product_ids: list[str]
    status_editorial: str | None = None
    status_publicacao: str | None = None


@router.get("/products")
def ops_list_products(
    brand: str | None = None,
    status_editorial: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 30,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    q = session.query(ProductORM)
    if brand:
        q = q.filter(ProductORM.brand_slug == brand)
    if status_editorial:
        q = q.filter(ProductORM.status_editorial == status_editorial)
    if search:
        q = q.filter(ProductORM.product_name.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(ProductORM.confidence.asc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [
            {
                "id": p.id, "product_name": p.product_name, "brand_slug": p.brand_slug,
                "verification_status": p.verification_status,
                "status_operacional": p.status_operacional, "status_editorial": p.status_editorial,
                "status_publicacao": p.status_publicacao, "confidence": p.confidence,
                "assigned_to": p.assigned_to,
            }
            for p in items
        ],
        "total": total, "page": page, "per_page": per_page,
    }


# --- IMPORTANT: batch endpoint BEFORE parameterized {product_id} ---

@router.patch("/products/batch")
def ops_batch_update(
    body: BatchStatusUpdate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    products = session.query(ProductORM).filter(ProductORM.id.in_(body.product_ids)).all()
    if len(products) != len(body.product_ids):
        raise HTTPException(status_code=400, detail="Some product IDs not found")
    updates = {}
    if body.status_editorial:
        updates["status_editorial"] = body.status_editorial
    if body.status_publicacao:
        updates["status_publicacao"] = body.status_publicacao
    for product in products:
        old_values = {f: getattr(product, f) for f in updates}
        for field, value in updates.items():
            setattr(product, field, value)
        create_revisions(session, "product", product.id, old_values, updates, user["sub"], "human")
    session.commit()
    return {"status": "ok", "updated": len(products)}


@router.get("/products/{product_id}/history")
def ops_product_history(
    product_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    revisions = get_entity_history(session, "product", product_id)
    return {
        "revisions": [
            {
                "revision_id": r.revision_id,
                "field_name": r.field_name,
                "old_value": r.old_value,
                "new_value": r.new_value,
                "changed_by": r.changed_by,
                "change_source": r.change_source,
                "change_reason": r.change_reason,
                "created_at": str(r.created_at),
            }
            for r in revisions
        ]
    }


@router.patch("/products/{product_id}")
def ops_patch_product(
    product_id: str,
    body: OpsProductUpdate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    product = session.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = body.model_dump(exclude_none=True)
    old_values = {f: getattr(product, f) for f in updates}
    for field, value in updates.items():
        setattr(product, field, value)
    create_revisions(session, "product", product_id, old_values, updates, user["sub"], "human")
    session.commit()
    return {"status": "ok", "product_id": product_id}
