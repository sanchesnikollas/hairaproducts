"""Moon AI — analyzes a product's INCI vs a hair profile.

Input:
  - inci: list of ingredient names (any language) OR product_id
  - hair_types: list of hair_type slugs (e.g., ["cacheado", "seco"])

Output:
  - score: -1.0 to +1.0 (overall compatibility)
  - breakdown: per-ingredient score with reasons
  - alerts: top concerns
  - benefits: top positive findings
"""
from __future__ import annotations

import json
import logging
import unicodedata
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.dependencies import is_multi_db, get_router, get_ops_session
from src.api.auth import get_current_user
from src.core.moon_ai import analyze_compatibility_ai
from src.storage.database import get_engine
from src.storage.ops_models import HairProfileORM
from sqlalchemy.orm import Session as SASession

logger = logging.getLogger("haira.moon")
router = APIRouter(prefix="/moon", tags=["moon"])


def _get_session():
    if is_multi_db():
        # In multi-DB mode the central DB has ingredients/aliases
        from src.storage.db_router import DatabaseRouter
        engine = get_engine()  # central DB
    else:
        engine = get_engine()
    with SASession(engine) as session:
        yield session


def normalize(name: str) -> str:
    if not name:
        return ""
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return n.lower().strip()


class AnalyzeRequest(BaseModel):
    inci: list[str] | None = None
    product_id: str | None = None
    hair_types: list[str]
    use_ai: bool = False  # quando True, anexa análise consultiva da IA (camada sobre o rule-based)


@router.post("/analyze")
def analyze(body: AnalyzeRequest, session: Session = Depends(_get_session)):
    """Analyze INCI list or product against hair_types profile."""
    if not body.inci and not body.product_id:
        raise HTTPException(status_code=400, detail="Provide inci or product_id")
    if not body.hair_types:
        raise HTTPException(status_code=400, detail="hair_types is required")

    # Resolve INCI list from product_id if needed
    ingredient_names = body.inci or []
    product_meta: dict = {}
    if body.product_id and not body.inci:
        rows = session.execute(text("""
            SELECT i.canonical_name
            FROM product_ingredients pi
            JOIN ingredients i ON pi.ingredient_id = i.id
            WHERE pi.product_id = :pid
            ORDER BY pi.position
        """), {"pid": body.product_id}).fetchall()
        ingredient_names = [r.canonical_name for r in rows]
        # Fallback: alguns produtos guardam INCI como JSON em products.inci_ingredients
        if not ingredient_names:
            prow = session.execute(text(
                "SELECT inci_ingredients FROM products WHERE id = :pid"
            ), {"pid": body.product_id}).first()
            if prow and prow.inci_ingredients:
                try:
                    parsed = json.loads(prow.inci_ingredients)
                    if isinstance(parsed, list):
                        ingredient_names = [str(x) for x in parsed]
                except (json.JSONDecodeError, TypeError):
                    pass
        if not ingredient_names:
            raise HTTPException(status_code=404, detail="No ingredients found for product")

    # Metadados do produto (pra contexto da IA) — best-effort, não bloqueia
    if body.product_id:
        try:
            meta = session.execute(text("""
                SELECT product_name, product_type_normalized, description
                FROM products WHERE id = :pid
            """), {"pid": body.product_id}).first()
            if meta:
                product_meta = {
                    "name": meta.product_name,
                    "product_type": meta.product_type_normalized,
                    "description": meta.description,
                }
        except Exception:  # noqa: BLE001
            product_meta = {}

    # Match each ingredient name to canonical (via name or alias)
    matched_categories: list[tuple[str, str | None, int]] = []
    # (input_name, category, position_index)
    for idx, name in enumerate(ingredient_names):
        # Try direct name match
        row = session.execute(text("""
            SELECT id, canonical_name, category FROM ingredients
            WHERE LOWER(canonical_name) = LOWER(:n)
            LIMIT 1
        """), {"n": name}).first()
        if not row:
            # Try alias
            row = session.execute(text("""
                SELECT i.id, i.canonical_name, i.category
                FROM ingredient_aliases a JOIN ingredients i ON a.ingredient_id = i.id
                WHERE LOWER(a.alias) = LOWER(:n)
                LIMIT 1
            """), {"n": name}).first()
        if not row:
            # Normalized name match
            norm = normalize(name)
            row = session.execute(text("""
                SELECT id, canonical_name, category FROM ingredients
                WHERE LOWER(canonical_name) = :norm
                LIMIT 1
            """), {"norm": norm}).first()
        if row:
            matched_categories.append((name, row.category, idx))
        else:
            matched_categories.append((name, None, idx))

    # Fetch compatibility rules for the requested hair_types
    rules_rows = session.execute(text("""
        SELECT category, hair_type, score, reason
        FROM ingredient_category_compatibility
        WHERE hair_type IN :hts
    """).bindparams(__import__("sqlalchemy").bindparam("hts", expanding=True)),
                                  {"hts": body.hair_types}).fetchall()
    rules: dict[tuple[str, str], dict] = {}
    for r in rules_rows:
        rules[(r.category, r.hair_type)] = {"score": r.score, "reason": r.reason}

    # Score each ingredient
    breakdown = []
    benefits = []
    alerts = []
    score_sum = 0.0
    weight_sum = 0.0

    n = len(matched_categories)
    for name, cat, idx in matched_categories:
        # Position weight: top 5 ingredients = 1.0, fade to 0.2 at end
        weight = max(0.2, 1.0 - (idx / max(n, 1)) * 0.8)
        per_ingredient = {"name": name, "category": cat, "weight": round(weight, 2),
                          "matches": []}
        if cat:
            for ht in body.hair_types:
                rule = rules.get((cat, ht))
                if rule:
                    per_ingredient["matches"].append({
                        "hair_type": ht,
                        "score": rule["score"],
                        "reason": rule["reason"],
                    })
                    score_sum += rule["score"] * weight
                    weight_sum += weight
                    if rule["score"] >= 1:
                        benefits.append({"name": name, "category": cat,
                                         "hair_type": ht, "reason": rule["reason"]})
                    elif rule["score"] <= -1:
                        alerts.append({"name": name, "category": cat,
                                       "hair_type": ht, "reason": rule["reason"]})
        breakdown.append(per_ingredient)

    overall = score_sum / max(weight_sum, 1.0) if weight_sum else 0.0

    # Coverage stats
    matched = sum(1 for _, c, _ in matched_categories if c)
    inci_known = sum(1 for n, _, _ in matched_categories
                     if any(c is not None for nn, c, _ in matched_categories if nn == n))

    result = {
        "overall_score": round(overall, 2),
        "interpretation": _interpret(overall),
        "hair_types": body.hair_types,
        "ingredients_total": len(ingredient_names),
        "ingredients_categorized": matched,
        "coverage_pct": round(100 * matched / max(len(ingredient_names), 1), 1),
        "alerts": alerts[:10],
        "benefits": benefits[:10],
        "breakdown": breakdown,
        "ai_analysis": None,
    }

    # Camada IA opcional — consultiva, sobre o score rule-based. Degrada graciosamente.
    if body.use_ai:
        result["ai_analysis"] = analyze_compatibility_ai(
            product_ctx={
                "name": product_meta.get("name"),
                "product_type": product_meta.get("product_type"),
                "description": product_meta.get("description"),
                "inci": ingredient_names,
            },
            hair_types=body.hair_types,
            rule_result=result,
        )

    return result


def _interpret(score: float) -> str:
    if score >= 0.6:
        return "Altamente compatível com o perfil"
    if score >= 0.2:
        return "Compatível com algumas reservas"
    if score >= -0.2:
        return "Neutro — sem grandes benefícios ou alertas"
    if score >= -0.6:
        return "Cuidado — possíveis incompatibilidades"
    return "Não recomendado para este perfil"


@router.get("/categories")
def list_categories(session: Session = Depends(_get_session)):
    """List all ingredient categories with their compatibility rules."""
    rows = session.execute(text("""
        SELECT category, hair_type, score, reason
        FROM ingredient_category_compatibility
        ORDER BY category, hair_type
    """)).fetchall()
    by_cat: dict[str, list] = defaultdict(list)
    for r in rows:
        by_cat[r.category].append({
            "hair_type": r.hair_type, "score": r.score, "reason": r.reason
        })
    return {"categories": dict(by_cat)}


# ---------------------------------------------------------------------------
# Perfil capilar do usuário — alimenta a análise contextual do Moon.
# ---------------------------------------------------------------------------

class HairProfileBody(BaseModel):
    hair_types: list[str]
    notes: str | None = None


@router.get("/profile")
def get_profile(
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    """Carrega o perfil capilar salvo do usuário logado."""
    prof = session.query(HairProfileORM).filter(
        HairProfileORM.user_id == user["sub"]
    ).first()
    if not prof:
        return {"hair_types": [], "notes": None, "exists": False}
    try:
        hts = json.loads(prof.hair_types) if prof.hair_types else []
    except (json.JSONDecodeError, TypeError):
        hts = []
    return {"hair_types": hts, "notes": prof.notes, "exists": True}


@router.put("/profile")
def save_profile(
    body: HairProfileBody,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    """Salva (cria ou atualiza) o perfil capilar do usuário logado."""
    prof = session.query(HairProfileORM).filter(
        HairProfileORM.user_id == user["sub"]
    ).first()
    payload = json.dumps(body.hair_types, ensure_ascii=False)
    if prof:
        prof.hair_types = payload
        prof.notes = body.notes
    else:
        prof = HairProfileORM(user_id=user["sub"], hair_types=payload, notes=body.notes)
        session.add(prof)
    session.commit()
    return {"hair_types": body.hair_types, "notes": body.notes, "exists": True}
