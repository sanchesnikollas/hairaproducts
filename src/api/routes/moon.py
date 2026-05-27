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

import logging
import unicodedata
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.dependencies import is_multi_db, get_router
from src.storage.database import get_engine
from sqlalchemy.orm import Session as SASession

from src.core.hair_profile import HairProfileInput, derive_hair_types, profile_summary
from src.storage.hair_profile_repository import HairProfileRepository

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


def _resolve_product_inci(session: Session, product_id: str) -> list[str]:
    """INCI for a product. Prefer the normalized product_ingredients join;
    fall back to the products.inci_ingredients JSON column."""
    rows = session.execute(text("""
        SELECT i.canonical_name
        FROM product_ingredients pi
        JOIN ingredients i ON pi.ingredient_id = i.id
        WHERE pi.product_id = :pid
        ORDER BY pi.position
    """), {"pid": product_id}).fetchall()
    if rows:
        return [r.canonical_name for r in rows]
    raw = session.execute(
        text("SELECT inci_ingredients FROM products WHERE id = :pid"),
        {"pid": product_id},
    ).scalar()
    if not raw:
        return []
    import json
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return []
    if isinstance(data, list):
        return [str(x) for x in data]
    return []


def score_inci(session: Session, ingredient_names: list[str], hair_types: list[str]) -> dict:
    """Score an INCI list against engine hair_type slugs. Pure scoring core
    shared by /analyze and /chat."""
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
                                  {"hts": hair_types}).fetchall()
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
            for ht in hair_types:
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

    return {
        "overall_score": round(overall, 2),
        "interpretation": _interpret(overall),
        "hair_types": hair_types,
        "ingredients_total": len(ingredient_names),
        "ingredients_categorized": matched,
        "coverage_pct": round(100 * matched / max(len(ingredient_names), 1), 1),
        "alerts": alerts[:10],
        "benefits": benefits[:10],
        "breakdown": breakdown,
    }


@router.post("/analyze")
def analyze(body: AnalyzeRequest, session: Session = Depends(_get_session)):
    """Analyze an INCI list or product against a list of hair_type slugs."""
    if not body.inci and not body.product_id:
        raise HTTPException(status_code=400, detail="Provide inci or product_id")
    if not body.hair_types:
        raise HTTPException(status_code=400, detail="hair_types is required")
    ingredient_names = body.inci or []
    if body.product_id and not body.inci:
        ingredient_names = _resolve_product_inci(session, body.product_id)
        if not ingredient_names:
            raise HTTPException(status_code=404, detail="No ingredients found for product")
    return score_inci(session, ingredient_names, body.hair_types)


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


# ----------------------------------------------------------------------------
# Hair profile — the persisted questionnaire that feeds Moon
# ----------------------------------------------------------------------------
class ProfileRequest(HairProfileInput):
    user_id: str | None = None


def _profile_to_dict(row) -> dict:
    return {
        "profile_id": row.profile_id,
        "user_id": row.user_id,
        "curl_type": row.curl_type, "curl_subtype": row.curl_subtype,
        "color": row.color, "volume": row.volume, "thickness": row.thickness,
        "length": row.length, "scalp_oiliness": row.scalp_oiliness,
        "dryness_damage": row.dryness_damage,
        "chemical_treatments": row.chemical_treatments or [],
        "heat_usage": row.heat_usage, "extensions": row.extensions,
        "wash_frequency": row.wash_frequency, "sun_exposure": row.sun_exposure,
        "water_exposure": row.water_exposure, "scalp_issues": row.scalp_issues,
        "conditionals": row.conditionals or {},
        "derived_hair_types": row.derived_hair_types or [],
    }


@router.post("/profile")
def save_profile(body: ProfileRequest, session: Session = Depends(_get_session)):
    """Create or update a user's hair profile (one per user)."""
    repo = HairProfileRepository(session)
    data = HairProfileInput(**body.model_dump(exclude={"user_id"}))
    row = repo.upsert(body.user_id, data)
    return _profile_to_dict(row)


@router.get("/profile/{user_id}")
def get_profile(user_id: str, session: Session = Depends(_get_session)):
    repo = HairProfileRepository(session)
    row = repo.get_by_user(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="No profile for this user")
    return _profile_to_dict(row)


# ----------------------------------------------------------------------------
# Moon chat — conversational layer over profile + product analysis + catalog
# ----------------------------------------------------------------------------
def _fetch_alternatives(session: Session, hair_types: list[str],
                        product_type: str | None, exclude_id: str | None,
                        limit: int = 8) -> list[dict]:
    """Catalog candidates of the same type with verified INCI, scored against
    the profile. Returns the top-scoring few for Moon to recommend."""
    sql = """
        SELECT id, product_name, brand_slug, product_type_normalized, product_labels
        FROM products
        WHERE verification_status = 'verified_inci'
          AND inci_ingredients IS NOT NULL AND length(inci_ingredients) > 5
    """
    params: dict = {}
    if product_type:
        sql += " AND product_type_normalized = :pt"
        params["pt"] = product_type
    if exclude_id:
        sql += " AND id != :xid"
        params["xid"] = exclude_id
    sql += " LIMIT :lim"
    params["lim"] = limit
    rows = session.execute(text(sql), params).fetchall()

    scored = []
    for r in rows:
        inci = _resolve_product_inci(session, r.id)
        if not inci:
            continue
        result = score_inci(session, inci, hair_types)
        scored.append({
            "product_id": r.id, "name": r.product_name, "brand": r.brand_slug,
            "type": r.product_type_normalized,
            "score": result["overall_score"],
            "interpretation": result["interpretation"],
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:3]


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    user_id: str | None = None
    profile: HairProfileInput | None = None
    product_id: str | None = None
    inci: list[str] | None = None
    suggest_alternatives: bool = True


MOON_SYSTEM = (
    "Você é a Moon, a assistente capilar do app HAIRA. Fala português do Brasil, "
    "tom acolhedor, próximo e especialista — nunca robótico. Use no máximo um emoji "
    "🌙 por mensagem, com parcimônia. Seja concisa (2 a 5 frases). Baseie TODA "
    "recomendação no perfil capilar da pessoa e nos dados de INCI fornecidos; nunca "
    "invente ingredientes ou benefícios que não estejam no contexto. Quando houver "
    "alternativas no catálogo, cite-as pelo nome. Se faltar dado, diga o que falta."
)


@router.post("/chat")
def chat(body: ChatRequest, session: Session = Depends(_get_session)):
    """Conversational Moon: grounds an LLM reply in the user's profile, the
    analyzed product (if any) and scored catalog alternatives."""
    if not body.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    # Resolve profile (inline or persisted)
    profile = body.profile
    if profile is None and body.user_id:
        row = HairProfileRepository(session).get_by_user(body.user_id)
        if row:
            profile = HairProfileInput(
                curl_type=row.curl_type, curl_subtype=row.curl_subtype,
                color=row.color, volume=row.volume, thickness=row.thickness,
                length=row.length, scalp_oiliness=row.scalp_oiliness,
                dryness_damage=row.dryness_damage,
                chemical_treatments=row.chemical_treatments or [],
                heat_usage=row.heat_usage, extensions=row.extensions,
                wash_frequency=row.wash_frequency, sun_exposure=row.sun_exposure,
                water_exposure=row.water_exposure, scalp_issues=row.scalp_issues,
                conditionals=row.conditionals or {},
            )
    if profile is None:
        raise HTTPException(status_code=400, detail="Provide profile or a user_id with a saved profile")

    hair_types = derive_hair_types(profile)
    summary = profile_summary(profile)

    # Analyze the product in context (scanned or queried), if any
    analysis = None
    product_name = None
    product_type = None
    ingredient_names = body.inci or []
    if body.product_id and not ingredient_names:
        ingredient_names = _resolve_product_inci(session, body.product_id)
        prow = session.execute(
            text("SELECT product_name, product_type_normalized FROM products WHERE id = :pid"),
            {"pid": body.product_id},
        ).first()
        if prow:
            product_name, product_type = prow.product_name, prow.product_type_normalized
    if ingredient_names and hair_types:
        analysis = score_inci(session, ingredient_names, hair_types)

    alternatives = []
    if body.suggest_alternatives and hair_types:
        alternatives = _fetch_alternatives(session, hair_types, product_type, body.product_id)

    # Build the grounding context for the LLM
    ctx = [f"PERFIL CAPILAR: {summary}",
           f"slugs técnicos: {', '.join(hair_types) if hair_types else 'nenhum derivado'}"]
    if product_name:
        ctx.append(f"PRODUTO EM ANÁLISE: {product_name}")
    if analysis:
        ctx.append(
            f"ANÁLISE INCI (score {analysis['overall_score']:+.2f} — {analysis['interpretation']}; "
            f"cobertura {analysis['coverage_pct']}%). "
            f"Alertas: {[a['name'] + ': ' + a['reason'] for a in analysis['alerts'][:4]] or 'nenhum'}. "
            f"Benefícios: {[b['name'] + ': ' + b['reason'] for b in analysis['benefits'][:4]] or 'nenhum'}."
        )
    if alternatives:
        ctx.append("ALTERNATIVAS NO CATÁLOGO (mais compatíveis): " + "; ".join(
            f"{a['name']} ({a['brand']}, score {a['score']:+.2f})" for a in alternatives))

    context_block = "\n".join(ctx)
    llm_messages = [{"role": "user", "content": f"[CONTEXTO INTERNO — não repita literalmente]\n{context_block}"}]
    llm_messages += [{"role": m.role, "content": m.content} for m in body.messages]

    try:
        from src.core.llm import LLMClient
        reply = LLMClient().chat(MOON_SYSTEM, llm_messages)
    except Exception as e:  # noqa: BLE001
        logger.warning("Moon chat LLM failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Moon indisponível: {e}")

    return {
        "reply": reply,
        "profile_summary": summary,
        "hair_types": hair_types,
        "analysis": analysis,
        "alternatives": alternatives,
    }
