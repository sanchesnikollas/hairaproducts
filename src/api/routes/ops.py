from __future__ import annotations
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, or_, case
from sqlalchemy.orm import Session
from src.api.auth import get_current_user, require_admin
from src.api.dependencies import get_ops_session
from src.storage.orm_models import ProductORM, ProductIngredientORM
from src.storage.ops_models import RevisionHistoryORM
from src.core.revision_service import create_revisions, get_entity_history, count_entity_history
from src.core.confidence import calculate_confidence, CRITICAL_FIELDS

router = APIRouter(prefix="/ops", tags=["ops"])


def _recalculate_confidence(session: Session, product: ProductORM) -> None:
    """Recalculate and update a product's confidence score and factors."""
    fields = {f: getattr(product, f, None) for f in CRITICAL_FIELDS}
    total_ing = session.query(func.count(ProductIngredientORM.id)).filter(
        ProductIngredientORM.product_id == product.id
    ).scalar() or 0
    validated_ing = session.query(func.count(ProductIngredientORM.id)).filter(
        ProductIngredientORM.product_id == product.id,
        ProductIngredientORM.validation_status == "validated",
    ).scalar() or 0
    score, factors = calculate_confidence(fields, validated_ing, total_ing, product.status_editorial)
    product.confidence = score
    product.confidence_factors = factors


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
        .filter(ProductORM.verification_status != "quarantined")
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


StatusOperacional = Literal["bruto", "extraido", "normalizado", "parseado", "validado"]
StatusEditorial = Literal["pendente", "em_revisao", "aprovado", "corrigido", "rejeitado"]
StatusPublicacao = Literal["rascunho", "publicado", "despublicado", "arquivado"]


class OpsProductUpdate(BaseModel):
    product_name: str | None = None
    description: str | None = None
    usage_instructions: str | None = None
    composition: str | None = None
    inci_ingredients: list[str] | None = None
    product_category: str | None = None
    size_volume: str | None = None
    status_editorial: StatusEditorial | None = None
    status_publicacao: StatusPublicacao | None = None
    status_operacional: StatusOperacional | None = None


class OpsProductCreate(BaseModel):
    brand_slug: str
    product_name: str
    product_url: str | None = None
    description: str | None = None
    usage_instructions: str | None = None
    composition: str | None = None
    inci_ingredients: list[str] | None = None
    product_category: str | None = None
    image_url_main: str | None = None
    size_volume: str | None = None
    price: float | None = None


class BatchStatusUpdate(BaseModel):
    product_ids: list[str]
    status_editorial: StatusEditorial | None = None
    status_publicacao: StatusPublicacao | None = None


@router.get("/products")
def ops_list_products(
    brand: str | None = None,
    status_editorial: str | None = None,
    verification_status: str | None = None,
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
    if verification_status:
        q = q.filter(ProductORM.verification_status == verification_status)
    if search:
        q = q.filter(ProductORM.product_name.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(ProductORM.confidence.asc()).offset((page - 1) * per_page).limit(per_page).all()

    def _data_quality(p: ProductORM) -> dict:
        """Calculate which fields are present/missing for data quality indicator."""
        fields = {
            "nome": bool(p.product_name),
            "descricao": bool(p.description),
            "ingredientes": bool(p.inci_ingredients),
            "composicao": bool(p.composition),
            "modo_de_uso": bool(p.usage_instructions),
            "categoria": bool(p.product_category),
            "imagem": bool(p.image_url_main),
            "preco": p.price is not None,
        }
        filled = sum(1 for v in fields.values() if v)
        return {"fields": fields, "filled": filled, "total": len(fields), "pct": round(filled / len(fields) * 100)}

    return {
        "items": [
            {
                "id": p.id, "product_name": p.product_name, "brand_slug": p.brand_slug,
                "verification_status": p.verification_status,
                "status_operacional": p.status_operacional, "status_editorial": p.status_editorial,
                "status_publicacao": p.status_publicacao, "confidence": p.confidence,
                "assigned_to": p.assigned_to,
                "data_quality": _data_quality(p),
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
        _recalculate_confidence(session, product)
    session.commit()
    return {"status": "ok", "updated": len(products)}


@router.post("/products")
def ops_create_product(
    body: OpsProductCreate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    import uuid
    product_url = body.product_url or f"manual://{body.brand_slug}/{uuid.uuid4().hex[:8]}"
    existing = session.query(ProductORM).filter(ProductORM.product_url == product_url).first()
    if existing:
        raise HTTPException(status_code=409, detail="Product URL already exists")
    product = ProductORM(
        id=str(uuid.uuid4()),
        brand_slug=body.brand_slug,
        product_name=body.product_name,
        product_url=product_url,
        description=body.description,
        usage_instructions=body.usage_instructions,
        composition=body.composition,
        inci_ingredients=body.inci_ingredients,
        product_category=body.product_category,
        image_url_main=body.image_url_main,
        size_volume=body.size_volume,
        price=body.price,
        verification_status="catalog_only",
        status_operacional="bruto",
        status_editorial="pendente",
        status_publicacao="rascunho",
        extraction_method="manual",
    )
    _recalculate_confidence(session, product)
    session.add(product)
    create_revisions(session, "product", product.id, {}, {"product_name": body.product_name}, user["sub"], "human",
                     change_reason="Produto criado manualmente")
    session.commit()
    return {"status": "ok", "product_id": product.id}


@router.get("/products/{product_id}")
def ops_get_product(
    product_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    product = session.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    fields_quality = {
        "nome": bool(product.product_name),
        "descricao": bool(product.description),
        "ingredientes": bool(product.inci_ingredients),
        "composicao": bool(product.composition),
        "modo_de_uso": bool(product.usage_instructions),
        "categoria": bool(product.product_category),
        "imagem": bool(product.image_url_main),
        "preco": product.price is not None,
    }
    filled = sum(1 for v in fields_quality.values() if v)
    return {
        "id": product.id, "product_name": product.product_name, "brand_slug": product.brand_slug,
        "description": product.description, "usage_instructions": product.usage_instructions,
        "composition": product.composition,
        "product_category": product.product_category, "verification_status": product.verification_status,
        "inci_ingredients": product.inci_ingredients, "image_url_main": product.image_url_main,
        "status_operacional": product.status_operacional, "status_editorial": product.status_editorial,
        "status_publicacao": product.status_publicacao, "confidence": product.confidence,
        "confidence_factors": product.confidence_factors,
        "interpretation_data": product.interpretation_data,
        "application_data": product.application_data,
        "decision_data": product.decision_data,
        "assigned_to": product.assigned_to,
        "size_volume": product.size_volume,
        "price": product.price,
        "product_url": product.product_url,
        "extraction_method": product.extraction_method,
        "product_labels": product.product_labels,
        "data_quality": {"fields": fields_quality, "filled": filled, "total": len(fields_quality), "pct": round(filled / len(fields_quality) * 100)},
    }


@router.get("/products/{product_id}/history")
def ops_product_history(
    product_id: str,
    page: int = 1,
    per_page: int = 50,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    total = count_entity_history(session, "product", product_id)
    revisions = get_entity_history(session, "product", product_id, limit=per_page, offset=(page - 1) * per_page)
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
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
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
    # Auto-upgrade verification_status when INCI is manually entered
    if "inci_ingredients" in updates and updates["inci_ingredients"] and product.verification_status != "verified_inci":
        old_values["verification_status"] = product.verification_status
        updates["verification_status"] = "verified_inci"
        product.verification_status = "verified_inci"
    create_revisions(session, "product", product_id, old_values, updates, user["sub"], "human")
    _recalculate_confidence(session, product)
    session.commit()
    return {"status": "ok", "product_id": product_id, "confidence": product.confidence}


class ResolveRequest(BaseModel):
    decision: Literal["approve", "correct", "reject"]
    notes: str | None = None
    corrections: dict | None = None


@router.get("/inci-summary")
def ops_inci_summary(
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    rows = (
        session.query(
            ProductORM.brand_slug,
            func.count(ProductORM.id).label("total"),
            func.sum(case((ProductORM.verification_status == "catalog_only", 1), else_=0)).label("pending"),
            func.sum(case((ProductORM.verification_status == "verified_inci", 1), else_=0)).label("verified"),
        )
        .group_by(ProductORM.brand_slug)
        .order_by(func.sum(case((ProductORM.verification_status == "catalog_only", 1), else_=0)).desc())
        .all()
    )
    brands = []
    total_pending = 0
    for row in rows:
        pending = int(row.pending or 0)
        verified = int(row.verified or 0)
        total = int(row.total or 0)
        pct = round(verified / total * 100, 1) if total > 0 else 0.0
        brands.append({
            "brand_slug": row.brand_slug,
            "total": total,
            "pending": pending,
            "verified": verified,
            "pct": pct,
        })
        total_pending += pending
    return {"brands": brands, "total_pending": total_pending}


@router.get("/review-queue")
def get_review_queue(
    type: str | None = None,
    brand: str | None = None,
    page: int = 1,
    per_page: int = 20,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    from src.core.taxonomy import VALID_CATEGORIES

    q = session.query(ProductORM)
    # Excluir quarantined e produtos sem categoria capilar válida
    q = q.filter(ProductORM.verification_status != "quarantined")
    q = q.filter(
        or_(
            ProductORM.product_category.in_(VALID_CATEGORIES),
            ProductORM.verification_status == "verified_inci",
        )
    )
    if type == "low_confidence":
        q = q.filter(ProductORM.confidence < 50)
    elif type == "pending_editorial":
        q = q.filter(ProductORM.status_editorial.in_(["pendente", "rejeitado"]))
    else:
        # Default: both low confidence and pending editorial
        q = q.filter(
            or_(
                ProductORM.status_editorial.in_(["pendente", "rejeitado"]),
                ProductORM.confidence < 50,
            )
        )
    if brand:
        q = q.filter(ProductORM.brand_slug == brand)
    total = q.count()
    items = q.order_by(ProductORM.confidence.asc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [
            {
                "id": p.id, "product_name": p.product_name, "brand_slug": p.brand_slug,
                "status_editorial": p.status_editorial, "confidence": p.confidence,
                "verification_status": p.verification_status,
                "assigned_to": p.assigned_to,
                "created_at": str(p.created_at) if p.created_at else None,
            }
            for p in items
        ],
        "total": total, "page": page, "per_page": per_page,
    }


@router.post("/review-queue/{product_id}/start")
def start_review(
    product_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    product = session.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.assigned_to and product.assigned_to != user["sub"]:
        raise HTTPException(status_code=409, detail="Product already assigned to another reviewer")
    old_values = {"status_editorial": product.status_editorial, "assigned_to": product.assigned_to}
    product.status_editorial = "em_revisao"
    product.assigned_to = user["sub"]
    create_revisions(session, "product", product_id, old_values,
                     {"status_editorial": "em_revisao", "assigned_to": user["sub"]},
                     user["sub"], "human")
    session.commit()
    return {"status": "ok", "product_id": product_id}


@router.post("/review-queue/{product_id}/resolve")
def resolve_review(
    product_id: str,
    body: ResolveRequest,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    product = session.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    # Collect all old values and new values in one pass to avoid duplicate revisions
    all_old = {"status_editorial": product.status_editorial, "assigned_to": product.assigned_to}
    if body.decision == "approve":
        product.status_editorial = "aprovado"
        product.status_publicacao = "publicado"
        all_old["status_publicacao"] = product.status_publicacao
    elif body.decision == "correct":
        product.status_editorial = "corrigido"
        if body.corrections:
            for field, value in body.corrections.items():
                if hasattr(product, field):
                    all_old[field] = getattr(product, field)
                    setattr(product, field, value)
    elif body.decision == "reject":
        product.status_editorial = "rejeitado"
    product.assigned_to = None
    all_new = {k: getattr(product, k) for k in all_old}
    create_revisions(session, "product", product_id, all_old, all_new, user["sub"], "human",
                     change_reason=body.notes)
    _recalculate_confidence(session, product)
    session.commit()
    return {"status": "ok", "product_id": product_id, "decision": body.decision}


@router.post("/cleanup-ingredients")
def cleanup_ingredients(
    user: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    """Remove description/sentence text that was incorrectly stored as ingredients."""
    from src.storage.orm_models import ProductIngredientORM
    try:
        from src.storage.orm_models import IngredientAliasORM
    except ImportError:
        IngredientAliasORM = None

    patterns = [
        "canonical_name LIKE 'combinado %'", "canonical_name LIKE '% dos ingredientes%'",
        "canonical_name LIKE 'com um %'", "canonical_name LIKE 'a arte %'",
        "canonical_name LIKE 'protagonista %'", "canonical_name LIKE 'as frutas %'",
        "canonical_name LIKE 'como %' AND length(canonical_name) > 15",
        "canonical_name LIKE 'com %' AND length(canonical_name) > 20",
        "canonical_name LIKE 'e %' AND length(canonical_name) > 20 AND canonical_name NOT LIKE 'e-%'",
        "canonical_name LIKE 'a %' AND length(canonical_name) > 20 AND canonical_name NOT LIKE 'A-%'",
        "canonical_name LIKE 'o %' AND length(canonical_name) > 20",
        "canonical_name LIKE 'as %' AND length(canonical_name) > 15",
        "canonical_name LIKE 'os %' AND length(canonical_name) > 15",
        "canonical_name LIKE 'um %'", "canonical_name LIKE 'uma %'",
        "canonical_name LIKE 'para %' AND length(canonical_name) > 15",
        "canonical_name LIKE 'que %'", "canonical_name LIKE 'no %' AND length(canonical_name) > 15",
        "canonical_name LIKE '% se destacam%'", "canonical_name LIKE '% ressalta%'",
        "canonical_name LIKE '% irreverente%'", "canonical_name LIKE '% origem natural%'",
        "canonical_name LIKE '% design %'",
        "canonical_name LIKE '%aplicar%'", "canonical_name LIKE '%enxaguar%'",
        "canonical_name LIKE '%massagear%'", "canonical_name LIKE '%embalagem%'",
        "canonical_name LIKE '%informações%' AND length(canonical_name) > 15",
        "canonical_name LIKE '%conservar%'", "canonical_name LIKE '%não ingerir%'",
        "canonical_name LIKE '%fora do alcance%'", "canonical_name LIKE '%prazo de validade%'",
        "canonical_name LIKE '%registro anvisa%'",
        "canonical_name LIKE 'Ingredientes:%'", "canonical_name LIKE 'Ingredientes %'",
        "canonical_name LIKE '%.%:%' AND length(canonical_name) > 50",
        "canonical_name LIKE '%.' AND length(canonical_name) > 3",
        "canonical_name LIKE '%]' AND canonical_name NOT LIKE '%[%]'",
        "length(TRIM(canonical_name)) < 2",
    ]

    from src.storage.orm_models import IngredientORM
    deleted = 0
    for pattern in patterns:
        try:
            rows = session.execute(func.text(f"SELECT id FROM ingredients WHERE {pattern}")).fetchall()
        except Exception:
            continue
        for (rid,) in rows:
            session.query(ProductIngredientORM).filter(ProductIngredientORM.ingredient_id == rid).delete()
            if IngredientAliasORM:
                session.query(IngredientAliasORM).filter(IngredientAliasORM.ingredient_id == rid).delete()
            session.query(IngredientORM).filter(IngredientORM.id == rid).delete()
            deleted += 1

    # Also fix trailing dots and case dedup
    all_ings = session.query(IngredientORM).all()
    seen = {}
    merged = 0
    for ing in all_ings:
        key = ing.canonical_name.lower().strip().rstrip('.')
        if key in seen:
            # Merge
            session.query(ProductIngredientORM).filter(
                ProductIngredientORM.ingredient_id == ing.id
            ).update({"ingredient_id": seen[key]}, synchronize_session=False)
            if IngredientAliasORM:
                session.query(IngredientAliasORM).filter(IngredientAliasORM.ingredient_id == ing.id).delete()
            session.delete(ing)
            merged += 1
        else:
            seen[key] = ing.id

    session.commit()
    remaining = session.query(func.count(IngredientORM.id)).scalar()
    return {"deleted": deleted, "merged": merged, "remaining": remaining}


@router.get("/seals")
def get_seals_summary(
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    """Return all seals with product counts."""
    import json as _json
    rows = session.query(ProductORM.product_labels).filter(
        ProductORM.product_labels.isnot(None),
        ProductORM.product_labels != "null",
    ).all()

    seal_counts: dict[str, int] = {}
    for (raw,) in rows:
        try:
            labels = raw if isinstance(raw, dict) else _json.loads(raw)
            for seal in labels.get("detected", []):
                seal_counts[seal] = seal_counts.get(seal, 0) + 1
            for seal in labels.get("inferred", []):
                seal_counts[seal] = seal_counts.get(seal, 0) + 1
        except Exception:
            pass

    return {
        "seals": [
            {"name": name, "count": count}
            for name, count in sorted(seal_counts.items(), key=lambda x: -x[1])
        ],
        "total_products_with_seals": len([r for r in rows if r[0] and r[0] != "null"]),
    }


@router.get("/seals/{seal_name}/products")
def get_seal_products(
    seal_name: str,
    page: int = 1,
    per_page: int = 20,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    """Return products that have a specific seal."""
    import json as _json
    # Query all products with labels, then filter in Python
    # (JSON column filtering in SQLite is limited)
    q = session.query(ProductORM).filter(
        ProductORM.product_labels.isnot(None),
        ProductORM.product_labels != "null",
    )
    all_products = q.all()

    matching = []
    for p in all_products:
        try:
            labels = p.product_labels if isinstance(p.product_labels, dict) else _json.loads(p.product_labels)
            all_seals = labels.get("detected", []) + labels.get("inferred", [])
            if seal_name in all_seals:
                matching.append(p)
        except Exception:
            pass

    total = len(matching)
    start = (page - 1) * per_page
    page_items = matching[start:start + per_page]

    return {
        "seal": seal_name,
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": p.id,
                "product_name": p.product_name,
                "brand_slug": p.brand_slug,
                "image_url_main": p.image_url_main,
                "product_category": p.product_category,
                "verification_status": p.verification_status,
            }
            for p in page_items
        ],
    }


@router.post("/products/{product_id}/extract-from-photo")
async def extract_from_photo(
    product_id: str,
    file: UploadFile,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    """Upload a product photo and extract INCI + metadata using AI Vision."""
    import anthropic
    import base64
    import os
    import re
    import json as _json

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    product = session.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Read and validate image
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    mime = file.content_type or "image/jpeg"
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Unsupported image type")

    img_b64 = base64.standard_b64encode(content).decode()

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": img_b64}},
                {"type": "text", "text": """Extract product data from this hair/cosmetic product photo.
Return ONLY valid JSON with these fields:
{
  "product_name": "full product name if visible",
  "brand": "brand name if visible",
  "inci_ingredients": ["ingredient1", "ingredient2", ...],
  "product_category": "shampoo|condicionador|mascara|tratamento|leave_in|oleo_serum|styling|coloracao|kit|null",
  "size_volume": "e.g. 300ml",
  "description": "product description if visible"
}
Only extract what is clearly readable. Use null for anything not visible.
For INCI, extract the complete list in order. Keep original language (Portuguese or English/Latin INCI names).
"""}
            ],
        }],
    )

    raw = message.content[0].text.strip()
    # Parse JSON from response
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        return {"status": "error", "message": "Could not parse AI response", "raw": raw[:500]}

    try:
        extracted = _json.loads(match.group())
    except _json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON from AI", "raw": raw[:500]}

    return {
        "status": "ok",
        "product_id": product_id,
        "current": {
            "product_name": product.product_name,
            "brand_slug": product.brand_slug,
            "inci_ingredients": product.inci_ingredients,
            "product_category": product.product_category,
            "size_volume": product.size_volume,
            "description": product.description,
        },
        "extracted": extracted,
        "source": "photo_vision",
        "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
    }


@router.post("/products/create-from-photo")
async def create_product_from_photo(
    file: UploadFile,
    brand_slug: str = "",
    user: dict = Depends(get_current_user),
):
    """Upload a product photo to create a new product. Returns extracted data for review."""
    import anthropic
    import base64
    import os
    import re
    import json as _json

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    mime = file.content_type or "image/jpeg"
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Unsupported image type")

    img_b64 = base64.standard_b64encode(content).decode()

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": img_b64}},
                {"type": "text", "text": """Extract ALL product data from this hair/cosmetic product packaging photo.
Return ONLY valid JSON:
{
  "product_name": "full product name",
  "brand": "brand name",
  "inci_ingredients": ["ingredient1", "ingredient2", ...],
  "product_category": "shampoo|condicionador|mascara|tratamento|leave_in|oleo_serum|styling|coloracao|kit|null",
  "size_volume": "e.g. 300ml",
  "description": "product description/claims if visible"
}
Extract the COMPLETE INCI ingredient list in order. Keep original names.
Use null for anything not readable.
"""}
            ],
        }],
    )

    raw = message.content[0].text.strip()
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        return {"status": "error", "message": "Could not parse AI response"}

    try:
        extracted = _json.loads(match.group())
    except _json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON from AI"}

    if brand_slug:
        extracted["brand_slug"] = brand_slug

    return {
        "status": "ok",
        "extracted": extracted,
        "source": "photo_vision",
        "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
    }
