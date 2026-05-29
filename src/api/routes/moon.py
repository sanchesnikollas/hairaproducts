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
from src.storage.moon_models import MoonFeedbackORM, MoonConversationORM, MoonMessageORM

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
# In-memory indexes (process-lifetime cache). Ingredients/rules change rarely.
_CAT_INDEX: dict[str, str] | None = None      # normalized ingredient name -> category
_RULES_INDEX: dict[tuple[str, str], int] | None = None  # (category, hair_type) -> score


def _ensure_indexes(session: Session) -> tuple[dict, dict]:
    global _CAT_INDEX, _RULES_INDEX
    if _CAT_INDEX is None:
        idx: dict[str, str] = {}
        for r in session.execute(text(
            "SELECT canonical_name, category FROM ingredients WHERE category IS NOT NULL"
        )).fetchall():
            idx[r.canonical_name.lower()] = r.category
            idx[normalize(r.canonical_name)] = r.category
        _CAT_INDEX = idx
    if _RULES_INDEX is None:
        rules: dict[tuple[str, str], int] = {}
        for r in session.execute(text(
            "SELECT category, hair_type, score FROM ingredient_category_compatibility"
        )).fetchall():
            rules[(r.category, r.hair_type)] = r.score
        _RULES_INDEX = rules
    return _CAT_INDEX, _RULES_INDEX


def _score_fast(ingredient_names: list[str], hair_types: list[str],
                cat_index: dict, rules: dict) -> tuple[float, int]:
    """In-memory scoring (no SQL) for ranking a large candidate pool.
    Mirrors score_inci's weighting. Returns (overall_score, matched_count)."""
    n = len(ingredient_names)
    score_sum = weight_sum = 0.0
    matched = 0
    for idx, name in enumerate(ingredient_names):
        cat = cat_index.get(name.lower()) or cat_index.get(normalize(name))
        if not cat:
            continue
        matched += 1
        weight = max(0.2, 1.0 - (idx / max(n, 1)) * 0.8)
        for ht in hair_types:
            rule = rules.get((cat, ht))
            if rule is not None:
                score_sum += rule * weight
                weight_sum += weight
    overall = score_sum / weight_sum if weight_sum else 0.0
    return round(overall, 2), matched


def _parse_inci(raw) -> list[str]:
    if not raw:
        return []
    import json
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return []
    return [str(x) for x in data] if isinstance(data, list) else []


def _fetch_alternatives(session: Session, hair_types: list[str],
                        product_type: str | None, exclude_id: str | None,
                        pool: int = 60) -> list[dict]:
    """Score a relevance-biased pool of verified-INCI catalog products against
    the profile and return the top matches. Biased toward richer INCI lists
    (more reliable scoring) instead of an arbitrary first-N slice."""
    if not hair_types:
        return []
    cat_index, rules = _ensure_indexes(session)

    # 3-layer non-hair guard (the catalog still mixes body/face/lip/perfume
    # products from multi-category brands; Moon must never recommend those):
    #   1) explicit pipeline flag: product_category='non_hair'
    #   2) name-based pipeline flag: hair_relevance_reason starts with non_hair
    #   3) name-keyword blacklist as a safety net for the gray tail
    sql = """
        SELECT id, product_name, brand_slug, product_type_normalized, inci_ingredients
        FROM products
        WHERE verification_status = 'verified_inci'
          AND inci_ingredients IS NOT NULL
          AND length(CAST(inci_ingredients AS TEXT)) > 20
          AND product_type_normalized IS NOT NULL
          AND (product_category IS NULL OR product_category != 'non_hair')
          AND (hair_relevance_reason IS NULL OR hair_relevance_reason NOT LIKE 'non_hair%')
          AND LOWER(product_name) NOT LIKE '%labial%'
          AND LOWER(product_name) NOT LIKE '%facial%'
          AND LOWER(product_name) NOT LIKE '%corporal%'
          AND LOWER(product_name) NOT LIKE '%perfume%'
          AND LOWER(product_name) NOT LIKE '%fps%'
          AND LOWER(product_name) NOT LIKE '%rímel%'
          AND LOWER(product_name) NOT LIKE '%rimel%'
          AND LOWER(product_name) NOT LIKE '%demaquilante%'
          AND LOWER(product_name) NOT LIKE '%sabonete em barra%'
          AND LOWER(product_name) NOT LIKE '%secativo%'
          AND LOWER(product_name) NOT LIKE '%desodorante%'
    """
    params: dict = {}
    if product_type:
        sql += " AND product_type_normalized = :pt"
        params["pt"] = product_type
    else:
        # Free chat (no product in context): don't recommend coloring inputs
        # (developer, bleach, dye) as care products — they score high on INCI
        # but aren't standalone recommendations.
        sql += " AND product_type_normalized NOT IN ('oxidante', 'descolorante', 'coloracao')"
    if exclude_id:
        sql += " AND id != :xid"
        params["xid"] = exclude_id
    # Richer INCI first → better-grounded scores, avoids near-empty lists scoring 0
    sql += " ORDER BY length(CAST(inci_ingredients AS TEXT)) DESC LIMIT :pool"
    params["pool"] = pool
    rows = session.execute(text(sql), params).fetchall()

    scored = []
    for r in rows:
        inci = _parse_inci(r.inci_ingredients)
        if len(inci) < 3:
            continue
        overall, matched = _score_fast(inci, hair_types, cat_index, rules)
        if matched < 2:  # too little signal to recommend confidently
            continue
        scored.append({
            "product_id": r.id, "name": r.product_name, "brand": r.brand_slug,
            "type": r.product_type_normalized,
            "score": overall, "interpretation": _interpret(overall),
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
    # Conversation persistence — if None, a new conversation is created.
    conversation_id: str | None = None
    # How many previous turns to include in the LLM context. Default 8 keeps
    # the prompt cheap while giving Moon enough memory for follow-ups.
    history_turns: int = 8


import re

# Intent routing — keep the LLM focused (and tokens cheap) by injecting only the
# context that the question type actually needs. Detection is heuristic (regex
# over the last user message) — fast, free, deterministic, easy to tweak.
# Regexes intencionalmente sem `\b` ao final — usamos prefixos que matcham
# variações ("cronogra" pega cronograma; "suger" pega sugere/sugerir/sugeriu).
_SAUDE_KWS = re.compile(
    r"\b(queda|caspa|coceira|coca[nr]|co[cç]a[nr]|descama|vermelh|dor(\s|$)|dor(ido|imento)|"
    r"ferida|alergi|alopec|dermatite|sebor|psor[ií]ase|inflama|infec)",
    re.I,
)
_ROTINA_KWS = re.compile(
    r"\b(cronogra|rotina|protocol|frequ[êe]ncia|hidrata[cç][aã]o|nutri[cç][aã]o|"
    r"reconstru[cç][aã]o|low.?poo|no.?poo|co.?wash|umecta|cuidad|finaliz|"
    r"como.+cuid|qual.+cuid)",
    re.I,
)
_ANALISE_KWS = re.compile(
    r"\b(esse|este|esta|essa|aqui|inci|composi[cç][aã]o|ingrediente)",
    re.I,
)
_RECOMENDACAO_KWS = re.compile(
    r"\b(suger|sugest|indica|indique|indicar|recomend|qual.+(produto|shampoo|condicionador|"
    r"m[áa]scara|leave|creme)|preciso.+(de um|de uma)|qual.+combina|qual.+melhor|me.+passa)",
    re.I,
)


def _detect_intent(last_user_msg: str, has_product_context: bool) -> str:
    """Classify the user question to drive context construction.

    Returns one of: saude_couro, analise_produto, recomendacao, rotina_cuidado, geral.
    Order matters — saúde tem prioridade (segurança), depois caminhos com produto
    explícito, depois rotina, depois fallback.
    """
    msg = (last_user_msg or "").strip()
    if not msg:
        return "geral"
    if _SAUDE_KWS.search(msg):
        return "saude_couro"
    if has_product_context or _ANALISE_KWS.search(msg):
        # com produto em contexto, "esse" / "posso usar" → análise
        if has_product_context or re.search(r"\b(serve|posso|combina|bom|ruim|funciona)\b", msg, re.I):
            return "analise_produto"
    if _RECOMENDACAO_KWS.search(msg):
        return "recomendacao"
    if _ROTINA_KWS.search(msg):
        return "rotina_cuidado"
    return "geral"


_INTENT_ADDENDUMS: dict[str, str] = {
    "saude_couro": (
        "A pessoa descreve sintomas no couro cabeludo (queda, caspa, vermelhidão, dor, etc.). "
        "Sua resposta DEVE: (a) acolher com empatia; (b) NÃO sugerir produtos como tratamento; "
        "(c) redirecionar a uma avaliação dermatológica como primeiro passo; (d) só depois "
        "mencionar cuidados gerais que se alinhem ao perfil. Nunca diagnostique."
    ),
    "analise_produto": (
        "A pessoa quer avaliar um produto específico. Use os dados da ANÁLISE INCI e do PRODUTO "
        "no contexto interno como base principal da resposta. Cite alertas e benefícios concretos. "
        "Se houver ALTERNATIVAS MAIS COMPATÍVEIS no catálogo, ofereça-as ao final."
    ),
    "recomendacao": (
        "A pessoa pede sugestão de produto. Priorize as ALTERNATIVAS NO CATÁLOGO do contexto interno "
        "(produtos reais da Haira), citando 1-3 pelo nome. Justifique brevemente por que combinam com "
        "o perfil. Não invente produtos fora dessa lista."
    ),
    "rotina_cuidado": (
        "A pessoa pede orientação de cuidado, rotina, cronograma ou protocolo. Esta resposta deve "
        "vir DIRETO do CONHECIMENTO PROPRIETÁRIO HAIRA (material das Doutoras). Não traga alternativas "
        "de catálogo a menos que sejam citadas nominalmente no conteúdo. Cite a fonte ao final."
    ),
    "geral": (
        "Conversa geral — saudação, esclarecimento ou off-topic leve. Mantenha o tom Moon e seja "
        "concisa. Se for uma pergunta vaga sobre cabelo, peça o esclarecimento que falta."
    ),
}


MOON_SYSTEM = (
    "Você é a Moon, a assistente capilar do app HAIRA. Fala português do Brasil, "
    "tom acolhedor, próximo e especialista — nunca robótico. Use no máximo um emoji "
    "🌙 por mensagem, com parcimônia. Seja concisa (2 a 5 frases).\n\n"
    "REGRAS DE EMBASAMENTO (não negociáveis):\n"
    "1. PRIORIZE o bloco [CONHECIMENTO PROPRIETÁRIO HAIRA] em TODA recomendação "
    "de cuidado, rotina, protocolo, diagnóstico de necessidade capilar e análise. "
    "Esse conteúdo é fornecido pelas Doutoras da Haira; ele substitui o seu "
    "conhecimento geral sempre que houver sobreposição.\n"
    "2. Quando usar o conhecimento proprietário, cite ao final entre parênteses "
    "a fonte (ex.: \"(Rotinas e Produtos)\" ou \"(Haira-Regras)\"). Curto, sem floreio.\n"
    "3. Para análise de produto, baseie-se nos dados de INCI fornecidos no contexto; "
    "nunca invente ingredientes ou benefícios fora dele.\n"
    "4. Quando houver alternativas no catálogo, cite-as pelo nome.\n"
    "5. Se o conhecimento proprietário não cobrir a pergunta, diga isso explicitamente "
    "(\"essa não está no nosso material ainda\") em vez de improvisar como ChatGPT.\n"
    "6. Diagnóstico de saúde do couro (queda, dermatite, dor, ferida) → sempre "
    "redirecione a dermatologista.\n"
)


@router.post("/chat")
def chat(body: ChatRequest, session: Session = Depends(_get_session)):
    """Conversational Moon: grounds an LLM reply in the user's profile, the
    analyzed product (if any) and scored catalog alternatives. Persists the
    turn so reviewers can resume past conversations."""
    if not body.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    # Resolve or create the conversation. Auth on /moon/profile is HAIRA-155;
    # until then user_id is best-effort.
    conv: MoonConversationORM | None = None
    if body.conversation_id:
        conv = session.get(MoonConversationORM, body.conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="conversation_id not found")
    else:
        # Auto-title from the first user message (truncated)
        first_user = next((m.content for m in body.messages if m.role == "user"), "")
        title = (first_user.strip()[:80] or "Conversa com a Moon")
        conv = MoonConversationORM(user_id=body.user_id, title=title)
        session.add(conv)
        session.flush()  # ensure conv.conversation_id

    # Load previous persisted turns (history_turns most recent) so Moon remembers
    # the conversation across requests. Older turns are dropped; client doesn't
    # have to round-trip them.
    history: list[MoonMessageORM] = []
    if body.conversation_id:
        history = (
            session.query(MoonMessageORM)
            .filter(MoonMessageORM.conversation_id == conv.conversation_id)
            .order_by(MoonMessageORM.created_at.desc())
            .limit(max(0, body.history_turns) * 2)
            .all()
        )
        history.reverse()  # back to chronological

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

    # Detect intent from the latest user message + presence of product context.
    # The intent drives WHICH heavy context blocks we build (analysis, alternatives)
    # — we don't waste tokens scoring INCI for a "monte um cronograma" question,
    # and we always force a safety redirect for "saude_couro".
    last_user = next((m.content for m in reversed(body.messages) if m.role == "user"), "")
    intent = _detect_intent(
        last_user_msg=last_user,
        has_product_context=bool(body.product_id or body.inci),
    )

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

    # INCI analysis: only when there's a product AND the intent will use it
    needs_inci_analysis = intent in {"analise_produto", "recomendacao"} and ingredient_names
    if needs_inci_analysis and hair_types:
        analysis = score_inci(session, ingredient_names, hair_types)

    # Alternatives: skip for pure routine/care/safety conversations — they
    # distract the LLM and burn tokens without value.
    alternatives = []
    wants_alternatives = (
        body.suggest_alternatives and hair_types
        and intent in {"analise_produto", "recomendacao"}
    )
    if wants_alternatives:
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
    # Histórico persistido (Moon lembra do que foi falado antes nesta conversa)
    for h in history:
        llm_messages.append({"role": h.role, "content": h.content})
    # Mensagens do request atual (último turno)
    llm_messages += [{"role": m.role, "content": m.content} for m in body.messages]

    # Intent-specific system addendum — anchors the LLM to the right behavior
    # for the type of question, without rewriting the whole MOON_SYSTEM.
    system_prompt = MOON_SYSTEM
    addendum = _INTENT_ADDENDUMS.get(intent)
    if addendum:
        system_prompt = MOON_SYSTEM + "\n\n[INTENÇÃO DETECTADA]\n" + addendum

    # Doutoras knowledge base — cached at the Anthropic prompt cache (5min TTL)
    # so the per-turn cost stays trivial despite ~45k tokens always present.
    from src.core.knowledge_base import load_knowledge_base
    kb = load_knowledge_base()

    try:
        from src.core.llm import LLMClient
        reply = LLMClient().chat(
            system=system_prompt, messages=llm_messages,
            cached_prefix=kb.system_block or None,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Moon chat LLM failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Moon indisponível: {e}")

    # Persist this turn (user msg + assistant reply) and bump last_message_at.
    from datetime import datetime, timezone
    for m in body.messages:
        session.add(MoonMessageORM(
            conversation_id=conv.conversation_id, role=m.role, content=m.content,
        ))
    session.add(MoonMessageORM(
        conversation_id=conv.conversation_id, role="assistant", content=reply,
        intent=intent, kb_sources=kb.sources,
        analysis=analysis, alternatives=alternatives or None,
    ))
    conv.last_message_at = datetime.now(timezone.utc)
    session.commit()

    return {
        "reply": reply,
        "conversation_id": conv.conversation_id,
        "intent": intent,
        "profile_summary": summary,
        "hair_types": hair_types,
        "analysis": analysis,
        "alternatives": alternatives,
        "kb_sources": kb.sources,
    }


# ----------------------------------------------------------------------------
# Feedback — reviewer 👍/👎 on Moon replies (north-star metric source)
# ----------------------------------------------------------------------------
class FeedbackRequest(BaseModel):
    rating: str                       # "up" | "down"
    message_content: str              # the Moon reply being rated
    user_message: str | None = None   # what the user had asked
    profile_snapshot: dict | None = None
    product_id: str | None = None
    comment: str | None = None
    user_id: str | None = None


@router.post("/feedback", status_code=201)
def submit_feedback(body: FeedbackRequest, session: Session = Depends(_get_session)):
    if body.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")
    row = MoonFeedbackORM(
        user_id=body.user_id, rating=body.rating,
        message_content=body.message_content, user_message=body.user_message,
        profile_snapshot=body.profile_snapshot, product_id=body.product_id,
        comment=body.comment,
    )
    session.add(row)
    session.commit()
    return {"feedback_id": row.feedback_id}


@router.get("/feedback/summary")
def feedback_summary(session: Session = Depends(_get_session)):
    """North-star metric: % of Moon replies rated useful, plus recent down-votes."""
    up = session.query(MoonFeedbackORM).filter(MoonFeedbackORM.rating == "up").count()
    down = session.query(MoonFeedbackORM).filter(MoonFeedbackORM.rating == "down").count()
    total = up + down
    recent_down = (
        session.query(MoonFeedbackORM)
        .filter(MoonFeedbackORM.rating == "down")
        .order_by(MoonFeedbackORM.created_at.desc())
        .limit(20).all()
    )
    return {
        "total": total, "up": up, "down": down,
        "useful_pct": round(100 * up / total, 1) if total else None,
        "recent_downvotes": [
            {"feedback_id": r.feedback_id, "user_message": r.user_message,
             "message_content": r.message_content, "comment": r.comment,
             "profile": r.profile_snapshot, "created_at": str(r.created_at)}
            for r in recent_down
        ],
    }


# ----------------------------------------------------------------------------
# Conversations — persisted Moon chat threads (sidebar list + retomar)
# ----------------------------------------------------------------------------
@router.get("/conversations")
def list_conversations(user_id: str | None = None,
                       limit: int = 30,
                       session: Session = Depends(_get_session)):
    """List most recent conversations, optionally filtered by user_id."""
    q = session.query(MoonConversationORM)
    if user_id:
        q = q.filter(MoonConversationORM.user_id == user_id)
    rows = q.order_by(MoonConversationORM.last_message_at.desc()).limit(limit).all()
    out = []
    for c in rows:
        n_messages = (
            session.query(MoonMessageORM)
            .filter(MoonMessageORM.conversation_id == c.conversation_id)
            .count()
        )
        out.append({
            "conversation_id": c.conversation_id,
            "user_id": c.user_id,
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
            "message_count": n_messages,
        })
    return {"conversations": out, "total": len(out)}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str,
                     session: Session = Depends(_get_session)):
    conv = session.get(MoonConversationORM, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Not found")
    msgs = (
        session.query(MoonMessageORM)
        .filter(MoonMessageORM.conversation_id == conversation_id)
        .order_by(MoonMessageORM.created_at.asc())
        .all()
    )
    return {
        "conversation_id": conv.conversation_id,
        "user_id": conv.user_id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        "messages": [
            {"message_id": m.message_id, "role": m.role, "content": m.content,
             "intent": m.intent, "kb_sources": m.kb_sources,
             "analysis": m.analysis, "alternatives": m.alternatives,
             "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in msgs
        ],
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str,
                        session: Session = Depends(_get_session)):
    conv = session.get(MoonConversationORM, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Not found")
    # Cascade messages then convo
    session.query(MoonMessageORM).filter(
        MoonMessageORM.conversation_id == conversation_id
    ).delete(synchronize_session=False)
    session.delete(conv)
    session.commit()
    return None
