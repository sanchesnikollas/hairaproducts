"""Derive a product's factual role in a hair-care routine (cronograma) from INCI.

Only FACTUAL signals live here — grounded in chemistry / existing config:
  - step                  : routine slot, from function_objective
  - cleansing_strength    : intensa (sulfate) | suave (mild surfactant) | None
  - has_insoluble_silicone: builds up, needs stronger cleansing (silicones.yaml)
  - has_drying_alcohol    : volatile drying alcohol present (allergens.yaml)

Editorial buckets (e.g. "conditioning weight", alternation rules, frequency) are
deliberately NOT inferred here — they belong to the Compêndio (Fernanda Torres),
which the Moon chat grounds against at assembly time. Keeping this layer factual
preserves the trust guarantee of the Gold base.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_LABELS_DIR = Path(__file__).resolve().parents[2] / "config" / "labels"

# function_objective (config/functions.yaml vocab) -> routine step
_STEP_BY_FUNCTION = {
    "limpar": "lavar",
    "condicionar": "condicionar",
    "hidratar": "tratar",
    "nutrir": "tratar",
    "reconstruir": "tratar",
    "tratar": "tratar",
    "esfoliar": "tratar",
    "definir": "finalizar",
    "finalizar": "finalizar",
    "modelar": "finalizar",
    "proteger": "finalizar",
    "alisar": "transformar",
    "ondular": "transformar",
    "colorir": "transformar",
}

# Mild surfactants (curated) — gentle cleansing, the opposite of harsh sulfates.
_MILD_SURFACTANTS = {
    "cocamidopropyl betaine", "coco betaine", "coco-betaine",
    "coco glucoside", "decyl glucoside", "lauryl glucoside", "caprylyl glucoside",
    "sodium cocoyl isethionate", "sodium lauroyl methyl isethionate",
    "sodium cocoyl glycinate", "sodium lauroyl sarcosinate",
    "disodium laureth sulfosuccinate", "sodium methyl cocoyl taurate",
    "sodium cocoamphoacetate", "disodium cocoamphodiacetate",
}


def _norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFD", name or "")
    stripped = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip().lower().strip(" .,;:*")


@lru_cache(maxsize=1)
def _load_set(filename: str, key: str) -> frozenset[str]:
    import yaml

    path = _LABELS_DIR / filename
    if not path.exists():
        return frozenset()
    data = yaml.safe_load(path.read_text()) or {}
    return frozenset(_norm(x) for x in (data.get(key) or []) if x)


def _sulfates() -> frozenset[str]:
    return _load_set("surfactants.yaml", "low_poo_prohibited")


def _insoluble_silicones() -> frozenset[str]:
    return _load_set("silicones.yaml", "insoluble")


def derive_routine_role(inci_ingredients: list[str] | None, function_objective: str | None = None) -> dict:
    """Factual routine-role signals for a product. Safe with empty INCI."""
    norm = {_norm(x) for x in (inci_ingredients or []) if x}

    if norm & _sulfates():
        cleansing_strength = "intensa"
    elif norm & _MILD_SURFACTANTS:
        cleansing_strength = "suave"
    else:
        cleansing_strength = None

    has_insoluble_silicone = bool(norm & _insoluble_silicones())

    from src.core.allergen_detector import detect_allergens
    has_drying_alcohol = any(
        a["allergen_class"] == "drying_alcohol" for a in detect_allergens(inci_ingredients)
    )

    return {
        "step": _STEP_BY_FUNCTION.get((function_objective or "").lower()),
        "cleansing_strength": cleansing_strength,
        "has_insoluble_silicone": has_insoluble_silicone,
        "has_drying_alcohol": has_drying_alcohol,
    }
