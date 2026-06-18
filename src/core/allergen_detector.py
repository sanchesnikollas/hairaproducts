"""Detect allergens / sensitizers directly on a product's INCI list.

Serves the "alérgicos" use case: given an INCI list (from the catalog or read by
OCR off a physical label), return the allergens present so the AI can warn e.g.
"contém Limonene e Linalool — alérgenos de fragrância declarados (UE)".

Matching is by EXACT normalized INCI entry (lowercase, accent-stripped), so
"alcohol" flags a drying alcohol while "cetyl alcohol" (a fatty alcohol) does not.
Definitions live in config/allergens.yaml (data, not code).
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "allergens.yaml"

# Severity ordering for "worst severity" summaries.
_SEVERITY_RANK = {"info": 0, "caution": 1, "high": 2}


def _normalize(name: str) -> str:
    """Lowercase, strip accents, collapse spaces, drop trailing punctuation."""
    nfkd = unicodedata.normalize("NFD", name)
    stripped = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    cleaned = re.sub(r"\s+", " ", stripped).strip().lower()
    return cleaned.strip(" .,;:*")


@lru_cache(maxsize=1)
def _load_allergen_index() -> dict[str, dict]:
    """Build {normalized_name: {allergen_class, severity, note_pt}} from YAML."""
    import yaml

    index: dict[str, dict] = {}
    if not _CONFIG_PATH.exists():
        return index
    data = yaml.safe_load(_CONFIG_PATH.read_text()) or {}
    for allergen_class, cfg in data.items():
        severity = cfg.get("severity", "info")
        note_pt = cfg.get("note_pt", "")
        for name in cfg.get("names", []) or []:
            key = _normalize(str(name))
            if key:
                # First definition wins if a name appears under two classes.
                index.setdefault(key, {
                    "allergen_class": allergen_class,
                    "severity": severity,
                    "note_pt": note_pt,
                })
    return index


def detect_allergens(inci_ingredients: list[str] | None) -> list[dict]:
    """Return the allergens present in an INCI list.

    Each entry: {ingredient, allergen_class, severity, note_pt}. Deduplicated by
    (ingredient, allergen_class), ordered by descending severity then name.
    """
    if not inci_ingredients:
        return []
    index = _load_allergen_index()
    seen: set[tuple[str, str]] = set()
    found: list[dict] = []
    for raw in inci_ingredients:
        if not isinstance(raw, str):
            continue
        key = _normalize(raw)
        hit = index.get(key)
        if not hit:
            continue
        dedup_key = (key, hit["allergen_class"])
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        found.append({
            "ingredient": raw.strip(),
            "allergen_class": hit["allergen_class"],
            "severity": hit["severity"],
            "note_pt": hit["note_pt"],
        })
    found.sort(key=lambda a: (-_SEVERITY_RANK.get(a["severity"], 0), a["ingredient"].lower()))
    return found


def allergen_summary(inci_ingredients: list[str] | None) -> dict:
    """Compact summary for the AI/Gold contract.

    {count, worst_severity, classes: [...], items: [detect_allergens()...]}.
    """
    items = detect_allergens(inci_ingredients)
    worst = None
    for it in items:
        if worst is None or _SEVERITY_RANK.get(it["severity"], 0) > _SEVERITY_RANK.get(worst, 0):
            worst = it["severity"]
    return {
        "count": len(items),
        "worst_severity": worst,
        "classes": sorted({it["allergen_class"] for it in items}),
        "items": items,
    }
