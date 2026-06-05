"""
Classifier — heuristic inference for hair_type, audience_age, function_objective.

Strategy:
  1. Load controlled vocabularies from config/{hair_types,audience_age,functions}.yaml
  2. Match keywords (case-insensitive, accent-folded) against product_name + description
  3. Use product_category + INCI signals as fallback
  4. Return ClassificationResult with per-field confidence (0-1)

Confidence > 0.6 → trust heuristic; otherwise caller may invoke LLM fallback.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_HAIR_TYPES_PATH = _PROJECT_ROOT / "config" / "hair_types.yaml"
_AUDIENCE_AGE_PATH = _PROJECT_ROOT / "config" / "audience_age.yaml"
_FUNCTIONS_PATH = _PROJECT_ROOT / "config" / "functions.yaml"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    hair_type: list[str] | None = None
    audience_age: str | None = None
    function_objective: str | None = None
    confidence_per_field: dict[str, float] = field(default_factory=dict)
    method: str = "heuristic"  # heuristic | llm | manual
    matched_keywords: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "hair_type": self.hair_type,
            "audience_age": self.audience_age,
            "function_objective": self.function_objective,
            "confidence_per_field": self.confidence_per_field,
            "method": self.method,
            "matched_keywords": self.matched_keywords,
        }


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    return _strip_accents(text).lower()


def _word_match(text: str, keyword: str) -> bool:
    """Match keyword in text with word-boundary protection.

    Accepts optional plural suffix (s|es) on the keyword end so that 'danificado'
    matches 'danificados', 'cacho' matches 'cachos', etc. Avoids 'liso' matching 'estilo'.
    """
    if not keyword:
        return False
    pattern = r"(?:^|\W)" + re.escape(keyword.lower()) + r"(?:s|es)?(?:$|\W)"
    return bool(re.search(pattern, text))


# ---------------------------------------------------------------------------
# Vocabulary loaders (cached)
# ---------------------------------------------------------------------------

_vocab_cache: dict[str, dict] = {}


def _load_yaml(path: Path) -> dict:
    if str(path) in _vocab_cache:
        return _vocab_cache[str(path)]
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _vocab_cache[str(path)] = data
    return data


def load_hair_types() -> dict:
    return _load_yaml(_HAIR_TYPES_PATH)


def load_audience_age() -> dict:
    return _load_yaml(_AUDIENCE_AGE_PATH)


def load_functions() -> dict:
    return _load_yaml(_FUNCTIONS_PATH)


def _all_keywords(entry: dict) -> list[str]:
    """Combine PT + EN keywords, normalized."""
    kws_pt = entry.get("keywords_pt") or entry.get("keywords") or []
    kws_en = entry.get("keywords_en") or []
    return [_normalize(k) for k in (kws_pt + kws_en) if k]


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

def infer_hair_type(
    product_name: str | None,
    description: str | None = None,
    inci_ingredients: list[str] | None = None,
) -> tuple[list[str], float, list[str]]:
    """Return (matched_types, confidence, matched_keywords).

    Multi-valor: produtos podem ter múltiplos tipos. Confidence baseado em força do match.
    """
    vocab = load_hair_types()
    text = " ".join(filter(None, [_normalize(product_name), _normalize(description)]))
    if not text:
        return ([], 0.0, [])

    matched_types: list[str] = []
    matched_keywords: list[str] = []
    score_per_match = 0.0

    for type_slug, entry in vocab.items():
        keywords = _all_keywords(entry)
        for kw in keywords:
            if _word_match(text, kw):
                if type_slug not in matched_types:
                    matched_types.append(type_slug)
                    matched_keywords.append(kw)
                    score_per_match += 0.4 if kw in (product_name or "").lower() else 0.25
                break  # first kw match per type is enough

    confidence = min(1.0, score_per_match) if matched_types else 0.0
    return (matched_types, confidence, matched_keywords)


def infer_audience_age(
    product_name: str | None,
    description: str | None = None,
) -> tuple[str, float, list[str]]:
    """Return (audience_age_slug, confidence, matched_keywords).

    Default = adult (low confidence). Specific matches override.
    """
    vocab = load_audience_age()
    text = " ".join(filter(None, [_normalize(product_name), _normalize(description)]))

    # Order matters: under_3 > kids > teen (more specific first)
    priority_order = ["under_3", "kids", "teen"]
    for age_slug in priority_order:
        entry = vocab.get(age_slug, {})
        keywords = _all_keywords(entry)
        for kw in keywords:
            if _word_match(text, kw):
                # Higher confidence if match in product name
                in_name = _word_match(_normalize(product_name), kw)
                conf = 0.9 if in_name else 0.7
                return (age_slug, conf, [kw])

    # Default = adult, low confidence (just absence of kid/teen markers)
    return ("adult", 0.5, [])


def infer_function_objective(
    product_name: str | None,
    product_category: str | None = None,
    description: str | None = None,
) -> tuple[str | None, float, list[str]]:
    """Return (function_slug, confidence, matched_keywords).

    Strategy:
      1. Match product_category against category_match (high confidence)
      2. Match keywords in name/description (medium confidence)
    """
    vocab = load_functions()
    text = " ".join(filter(None, [_normalize(product_name), _normalize(description)]))
    cat = _normalize(product_category)

    # 1. Category match (deterministic, high confidence)
    if cat:
        for func_slug, entry in vocab.items():
            cat_matches = entry.get("category_match", [])
            if cat in [_normalize(c) for c in cat_matches]:
                return (func_slug, 0.9, [f"category:{cat}"])

    # 2. Keyword match in name (medium-high confidence)
    if text:
        for func_slug, entry in vocab.items():
            keywords = [_normalize(k) for k in entry.get("keywords_pt", []) + entry.get("keywords_en", [])]
            for kw in keywords:
                if _word_match(text, kw):
                    in_name = _word_match(_normalize(product_name), kw)
                    conf = 0.75 if in_name else 0.55
                    return (func_slug, conf, [kw])

    return (None, 0.0, [])


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def classify_product(
    product_name: str | None,
    description: str | None = None,
    product_category: str | None = None,
    inci_ingredients: list[str] | None = None,
) -> ClassificationResult:
    """Apply all heuristics. Caller decides whether to invoke LLM fallback."""
    hair_types, ht_conf, ht_kw = infer_hair_type(product_name, description, inci_ingredients)
    age, age_conf, age_kw = infer_audience_age(product_name, description)
    func, func_conf, func_kw = infer_function_objective(product_name, product_category, description)

    return ClassificationResult(
        hair_type=hair_types if hair_types else None,
        audience_age=age,
        function_objective=func,
        confidence_per_field={
            "hair_type": ht_conf,
            "audience_age": age_conf,
            "function_objective": func_conf,
        },
        method="heuristic",
        matched_keywords={
            "hair_type": ht_kw,
            "audience_age": age_kw,
            "function_objective": func_kw,
        },
    )
