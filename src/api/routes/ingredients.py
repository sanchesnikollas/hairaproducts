# src/api/routes/ingredients.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.storage.database import get_engine
from src.storage.repository import ProductRepository
from src.storage.orm_models import IngredientORM, ProductIngredientORM

router = APIRouter(tags=["ingredients"])


def _get_session(brand: str | None = Query(None)):
    from src.api.dependencies import is_multi_db, get_router
    if is_multi_db():
        if not brand:
            raise HTTPException(status_code=400, detail="brand query parameter required in multi-database mode")
        router = get_router()
        session = router.get_session(brand)
        try:
            yield session
        finally:
            session.close()
    else:
        from sqlalchemy.orm import Session as SASession
        engine = get_engine()
        with SASession(engine) as session:
            yield session


@router.get("/ingredients")
def list_ingredients(
    q: str | None = Query(None, description="Search query"),
    category: str | None = Query(None),
    limit: int = Query(50, le=200),
    session: Session = Depends(_get_session),
):
    repo = ProductRepository(session)
    if q:
        ingredients = repo.search_ingredients(q, limit=limit)
    else:
        query = session.query(IngredientORM)
        if category:
            query = query.filter_by(category=category)
        ingredients = query.limit(limit).all()

    return [
        {
            "id": ing.id,
            "canonical_name": ing.canonical_name,
            "inci_name": ing.inci_name,
            "category": ing.category,
            "product_count": session.query(ProductIngredientORM).filter_by(ingredient_id=ing.id).count(),
        }
        for ing in ingredients
    ]


@router.get("/ingredients/{ingredient_id}")
def get_ingredient(ingredient_id: str, session: Session = Depends(_get_session)):
    ing = session.get(IngredientORM, ingredient_id)
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    aliases = [a.alias for a in ing.aliases]
    product_count = session.query(ProductIngredientORM).filter_by(ingredient_id=ing.id).count()

    return {
        "id": ing.id,
        "canonical_name": ing.canonical_name,
        "inci_name": ing.inci_name,
        "cas_number": ing.cas_number,
        "category": ing.category,
        "safety_rating": ing.safety_rating,
        "aliases": aliases,
        "product_count": product_count,
    }
