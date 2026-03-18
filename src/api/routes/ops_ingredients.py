from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from src.api.auth import require_admin
from src.api.dependencies import get_ops_session
from src.storage.orm_models import IngredientORM, IngredientAliasORM, ProductIngredientORM
from src.core.revision_service import create_revisions

router = APIRouter(prefix="/ops/ingredients", tags=["ops-ingredients"])


class IngredientUpdate(BaseModel):
    canonical_name: str | None = None
    inci_name: str | None = None
    category: str | None = None
    safety_rating: str | None = None


class AliasCreate(BaseModel):
    alias: str
    language: str | None = None


@router.get("/gaps")
def get_gaps(
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    uncategorized = (
        session.query(IngredientORM)
        .filter(IngredientORM.category.is_(None))
        .order_by(IngredientORM.canonical_name)
        .all()
    )
    orphans = (
        session.query(
            ProductIngredientORM.raw_name,
            func.count(ProductIngredientORM.id).label("product_count"),
        )
        .join(IngredientORM, ProductIngredientORM.ingredient_id == IngredientORM.id)
        .filter(IngredientORM.category.is_(None))
        .group_by(ProductIngredientORM.raw_name)
        .order_by(func.count(ProductIngredientORM.id).desc())
        .limit(100)
        .all()
    )
    return {
        "uncategorized": [
            {"id": i.id, "canonical_name": i.canonical_name, "inci_name": i.inci_name}
            for i in uncategorized
        ],
        "orphan_raw_names": [
            {"raw_name": o.raw_name, "product_count": o.product_count}
            for o in orphans
        ],
    }


@router.patch("/{ingredient_id}")
def update_ingredient(
    ingredient_id: str,
    body: IngredientUpdate,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    ing = session.query(IngredientORM).filter(IngredientORM.id == ingredient_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    updates = body.model_dump(exclude_none=True)
    old_values = {f: getattr(ing, f) for f in updates}
    for field, value in updates.items():
        setattr(ing, field, value)
    create_revisions(session, "ingredient", ingredient_id, old_values, updates, admin["sub"], "human")
    session.commit()
    return {"status": "ok", "ingredient_id": ingredient_id}


@router.post("/{ingredient_id}/aliases", status_code=201)
def add_alias(
    ingredient_id: str,
    body: AliasCreate,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    ing = session.query(IngredientORM).filter(IngredientORM.id == ingredient_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    alias = IngredientAliasORM(ingredient_id=ingredient_id, alias=body.alias, language=body.language)
    session.add(alias)
    session.commit()
    return {"status": "ok", "alias_id": alias.id}


@router.delete("/{ingredient_id}/aliases/{alias_id}")
def delete_alias(
    ingredient_id: str,
    alias_id: str,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    alias = session.query(IngredientAliasORM).filter(
        IngredientAliasORM.id == alias_id,
        IngredientAliasORM.ingredient_id == ingredient_id,
    ).first()
    if not alias:
        raise HTTPException(status_code=404, detail="Alias not found")
    session.delete(alias)
    session.commit()
    return {"status": "ok"}
