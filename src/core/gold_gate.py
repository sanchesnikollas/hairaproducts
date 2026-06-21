"""Gold gate — the single, auditable definition of an AI-trustworthy product.

A product is GOLD only when it passes EVERY criterion below. This is the only
tier the Moon AI consumes. Gold can never be granted by a bare status flip
(see src/api/routes/quarantine.py): it must be earned through evaluate_gold.

The five required fields (user-defined strict bar):
    G1  inci_ingredients   verified, anti-marketing, strict (>=5 terms)
    G2  image              front/main image present
    G3  usage_instructions real how-to-use (action verb, not a tab label)
    G4  description        real prose (>=40 chars, not an INCI list / tab label)
    G5  product_category   in the controlled vocabulary

Plus disqualifiers that keep non-products out of the AI's reach without deleting:
    G6  not quarantined / hidden / non-hair
    G7  product name passes the positive quality check

Hard blockers (severity="error") prevent Gold and drop the product to `catalog`
(or `raw` when it is disqualified). Soft blockers (severity="warning") mean the
data is complete but a trust signal needs human eyes -> `gold_candidate`.
"""
from __future__ import annotations

from urllib.parse import urlparse

from src.core.field_validator import (
    IssueSeverity,
    is_real_usage_instructions,
    validate_product_fields,
    validate_product_name_quality,
)
from src.core.inci_validator import validate_inci_list
from src.core.models import GoldBlocker, GoldEvaluation, GoldStatus
from src.core.taxonomy import VALID_CATEGORIES

# At least this share of cleaned INCI terms must resolve to a known ingredient
# for the list to read as fully trustworthy. Below it the product is not
# rejected — it routes to human review (gold_candidate). Degrades gracefully as
# the ingredients table is backfilled.
MIN_KNOWN_INGREDIENT_RATIO = 0.6
# Below this, the "INCI" is almost certainly not an ingredient list (e.g. checkout
# text scraped into the field) — a HARD error so it drops to catalog for clean
# re-extraction, never a candidate. Between HARD and MIN it is a soft review signal.
HARD_MIN_KNOWN_INGREDIENT_RATIO = 0.3
MIN_DESCRIPTION_LEN = 40

# INCI provenance that, on its own, is not enough for Gold (needs grounding /
# dual-validation first). Anything else (jsonld, html_selector, js_dom, manual,
# external_enrichment) is accepted.
_LLM_ONLY_METHODS = {"llm_grounded"}


def _has_url(value) -> bool:
    if not value or not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return bool(parsed.scheme and parsed.netloc)


def _is_tab_label(text: str) -> bool:
    try:
        from src.extraction.section_classifier import _is_tab_nav_noise

        return _is_tab_nav_noise(text)
    except Exception:
        return False


def _known_ingredient_ratio(cleaned: list[str], session) -> tuple[float, int, int] | None:
    """Share of cleaned INCI terms found in the ingredients/aliases tables.

    Returns (ratio, n_known, n_total) or None when it cannot be computed
    (no session or no terms) — in which case the check is simply skipped.
    """
    if session is None or not cleaned:
        return None
    terms = sorted({t.strip().lower() for t in cleaned if t and t.strip()})
    if not terms:
        return None
    from sqlalchemy import func

    from src.storage.orm_models import IngredientAliasORM, IngredientORM

    found: set[str] = set()
    canon = (
        session.query(func.lower(IngredientORM.canonical_name))
        .filter(func.lower(IngredientORM.canonical_name).in_(terms))
        .all()
    )
    found.update(r[0] for r in canon if r[0])
    alias = (
        session.query(func.lower(IngredientAliasORM.alias))
        .filter(func.lower(IngredientAliasORM.alias).in_(terms))
        .all()
    )
    found.update(r[0] for r in alias if r[0])
    n_known = sum(1 for t in terms if t in found)
    return (n_known / len(terms), n_known, len(terms))


def _inci_provenance_grounded(product, session) -> bool:
    """True when the INCI has at least one non-LLM-only provenance.

    Checks ProductEvidenceORM for field_name='inci_ingredients' first, then
    falls back to product.extraction_method. Unknown provenance does not block.
    """
    if session is not None:
        pid = getattr(product, "id", None)
        if pid:
            from src.storage.orm_models import ProductEvidenceORM

            rows = (
                session.query(ProductEvidenceORM.extraction_method)
                .filter(
                    ProductEvidenceORM.product_id == pid,
                    ProductEvidenceORM.field_name == "inci_ingredients",
                )
                .all()
            )
            methods = {r[0] for r in rows if r[0]}
            if methods:
                return any(m not in _LLM_ONLY_METHODS for m in methods)
    method = getattr(product, "extraction_method", None)
    if method:
        return method not in _LLM_ONLY_METHODS
    return True  # unknown provenance — don't block on this alone


def evaluate_gold(product, session=None) -> GoldEvaluation:
    """Evaluate a product (ProductORM or ProductExtraction) against the Gold bar.

    `session` is optional: when provided, enables the known-ingredient-ratio and
    INCI-provenance trust signals (both soft). Without it the gate still runs all
    completeness + field-truthfulness checks, so it stays unit-testable offline.
    """
    blockers: list[GoldBlocker] = []
    report: dict = {}
    disqualified = False      # G6/G7 -> never Gold (raw)
    missing_or_invalid = False  # a required field missing/untruthful -> catalog
    soft = False              # trust signal needs human -> gold_candidate

    # --- G6: disqualifiers (kept out of the AI's reach, not deleted) ---
    if getattr(product, "verification_status", None) == "quarantined":
        blockers.append(GoldBlocker(code="quarantined", field="verification_status",
                                    message="Produto está quarentenado", severity="error"))
        disqualified = True
    if getattr(product, "is_hidden", False):
        blockers.append(GoldBlocker(code="hidden", field="is_hidden",
                                    message="Produto está oculto (soft-delete)", severity="error"))
        disqualified = True
    hrr = getattr(product, "hair_relevance_reason", None) or ""
    if hrr.startswith("non_hair"):
        blockers.append(GoldBlocker(code="non_hair", field="hair_relevance_reason",
                                    message=f"Classificado como não-capilar ({hrr})", severity="error"))
        disqualified = True

    # --- G7: name quality ---
    nq = validate_product_name_quality(getattr(product, "product_name", None))
    report["name_score"] = nq.score
    if not nq.is_valid:
        blockers.append(GoldBlocker(code="name_low_quality", field="product_name",
                                    message=f"Nome reprovado: {', '.join(nq.issues[:3]) or 'baixa qualidade'}",
                                    severity="error"))
        disqualified = True

    # --- G1: INCI verified (strict) ---
    inci = getattr(product, "inci_ingredients", None)
    inci = inci if isinstance(inci, list) else None
    if not inci:
        blockers.append(GoldBlocker(code="inci_missing", field="inci_ingredients",
                                    message="Sem lista de INCI", severity="error"))
        missing_or_invalid = True
    else:
        res = validate_inci_list(inci, has_section_context=False)
        report["inci_terms"] = len(res.cleaned)
        if not res.valid:
            blockers.append(GoldBlocker(code=f"inci_invalid:{res.rejection_reason}",
                                        field="inci_ingredients",
                                        message=f"INCI reprovado (estrito): {res.rejection_reason}",
                                        severity="error"))
            missing_or_invalid = True
        else:
            vr = validate_product_fields(inci_ingredients=inci)
            inci_errors = [i for i in vr.issues
                           if i.field == "inci_ingredients" and i.severity == IssueSeverity.ERROR]
            if inci_errors:
                blockers.append(GoldBlocker(code=inci_errors[0].code, field="inci_ingredients",
                                            message=inci_errors[0].message, severity="error"))
                missing_or_invalid = True
            else:
                inci_warns = [i for i in vr.issues
                              if i.field == "inci_ingredients" and i.severity == IssueSeverity.WARNING]
                if inci_warns:
                    blockers.append(GoldBlocker(code=inci_warns[0].code, field="inci_ingredients",
                                                message=inci_warns[0].message, severity="warning"))
                    soft = True
                kr = _known_ingredient_ratio(res.cleaned, session)
                if kr is not None:
                    ratio, n_known, n_total = kr
                    report["known_ingredient_ratio"] = round(ratio, 3)
                    if ratio < HARD_MIN_KNOWN_INGREDIENT_RATIO:
                        blockers.append(GoldBlocker(
                            code="inci_garbage", field="inci_ingredients",
                            message=(f"Só {n_known}/{n_total} ingredientes reconhecidos "
                                     f"(<{int(HARD_MIN_KNOWN_INGREDIENT_RATIO*100)}%) — INCI não confiável"),
                            severity="error"))
                        missing_or_invalid = True
                    elif ratio < MIN_KNOWN_INGREDIENT_RATIO:
                        blockers.append(GoldBlocker(
                            code="inci_low_known_ratio", field="inci_ingredients",
                            message=(f"Só {n_known}/{n_total} ingredientes reconhecidos "
                                     f"(<{int(MIN_KNOWN_INGREDIENT_RATIO*100)}%) — revisar"),
                            severity="warning"))
                        soft = True
                if not _inci_provenance_grounded(product, session):
                    blockers.append(GoldBlocker(
                        code="inci_llm_only", field="inci_ingredients",
                        message="INCI veio só de LLM sem fonte verificável — precisa validação",
                        severity="warning"))
                    soft = True

    # --- G2: image ---
    image = getattr(product, "image_url_front", None) or getattr(product, "image_url_main", None)
    if not _has_url(image):
        blockers.append(GoldBlocker(code="image_missing", field="image_url_main",
                                    message="Sem imagem do produto", severity="error"))
        missing_or_invalid = True

    # --- G3: how-to-use ---
    usage = getattr(product, "usage_instructions", None)
    if not is_real_usage_instructions(usage):
        code = "usage_missing" if not (usage and usage.strip()) else "usage_not_instructions"
        blockers.append(GoldBlocker(code=code, field="usage_instructions",
                                    message="Sem 'como usar' real (instrução com verbo de ação)",
                                    severity="error"))
        missing_or_invalid = True

    # --- G4: description ---
    desc = getattr(product, "description", None)
    if not desc or len(desc.strip()) < MIN_DESCRIPTION_LEN:
        blockers.append(GoldBlocker(code="desc_missing", field="description",
                                    message=f"Descrição ausente ou curta (<{MIN_DESCRIPTION_LEN})",
                                    severity="error"))
        missing_or_invalid = True
    elif _is_tab_label(desc):
        blockers.append(GoldBlocker(code="desc_is_label", field="description",
                                    message="Descrição é rótulo de aba, não prosa", severity="error"))
        missing_or_invalid = True
    else:
        vr2 = validate_product_fields(description=desc)
        desc_errors = [i for i in vr2.issues
                       if i.field == "description" and i.severity == IssueSeverity.ERROR]
        if desc_errors:
            blockers.append(GoldBlocker(code=desc_errors[0].code, field="description",
                                        message=desc_errors[0].message, severity="error"))
            missing_or_invalid = True

    # --- G5: category ---
    cat = getattr(product, "product_category", None)
    if cat not in VALID_CATEGORIES:
        blockers.append(GoldBlocker(code="category_invalid", field="product_category",
                                    message=f"Categoria inválida/ausente ({cat!r})", severity="error"))
        missing_or_invalid = True

    # --- Kit/combo: not a single product the OCR can scan (client feedback) ---
    # Kept in the catalog, but never Gold — its INCI is the union of several
    # products and can't answer a single-bottle lookup.
    if getattr(product, "is_kit", False):
        blockers.append(GoldBlocker(code="is_kit", field="is_kit",
                                    message="Kit/combo não é produto único para OCR/IA", severity="error"))
        missing_or_invalid = True

    # --- verdict ---
    if disqualified:
        status = GoldStatus.RAW
    elif missing_or_invalid:
        status = GoldStatus.CATALOG
    elif soft:
        status = GoldStatus.GOLD_CANDIDATE
    else:
        status = GoldStatus.GOLD

    return GoldEvaluation(gold_status=status, blockers=blockers, field_report=report)
