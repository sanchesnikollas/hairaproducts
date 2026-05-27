"""Hair profile domain layer: schema, slug derivation and human summary.

The capture flow (Figma "Plano Cliente") collects a rich profile, but Moon's
scoring engine (`ingredient_category_compatibility`) only understands a fixed
set of hair_type slugs. `derive_hair_types` bridges the two.

Known engine slugs (from the compatibility table):
  liso, cacheado, crespo, oleoso, seco, normal, com_quimica, tingido,
  danificado, sensibilizado, fino

Taxonomy gaps (documented, intentionally unmapped to avoid bad signal):
  - "ondulado" curvature has no engine slug -> contributes no curvature slug
  - "grosso" thickness has no engine slug
  - color / extensions / sun-water exposure are recorded but not scored yet
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

KNOWN_HAIR_TYPE_SLUGS = {
    "liso", "cacheado", "crespo", "oleoso", "seco", "normal",
    "com_quimica", "tingido", "danificado", "sensibilizado", "fino",
}


class HairProfileInput(BaseModel):
    """Answers from the capture flow. Every field optional — partial profiles
    are valid (the flow can be resumed)."""
    curl_type: Optional[str] = None          # liso|ondulado|cacheado|crespo|transicao
    curl_subtype: Optional[str] = None       # 1A..4C | nao_sei
    color: Optional[str] = None
    volume: Optional[str] = None
    thickness: Optional[str] = None          # finos|medios|grossos
    length: Optional[str] = None
    scalp_oiliness: Optional[str] = None     # baixa|normal|alta
    dryness_damage: Optional[str] = None     # nao|um_pouco|bastante
    chemical_treatments: list[str] = Field(default_factory=list)  # coloracao|descoloracao|alisamento
    heat_usage: Optional[str] = None
    extensions: Optional[str] = None
    wash_frequency: Optional[str] = None
    sun_exposure: Optional[str] = None       # baixa|moderada|alta
    water_exposure: Optional[str] = None     # nunca|ocasional|frequente
    scalp_issues: Optional[bool] = None
    conditionals: dict = Field(default_factory=dict)
    raw_answers: dict = Field(default_factory=dict)


def derive_hair_types(p: HairProfileInput) -> list[str]:
    """Map a rich profile onto engine slugs. Deterministic, order-stable."""
    slugs: list[str] = []

    def add(s: str) -> None:
        if s in KNOWN_HAIR_TYPE_SLUGS and s not in slugs:
            slugs.append(s)

    # Curvature — prefer the precise subtype when available
    sub = (p.curl_subtype or "").upper()
    if sub and sub != "NAO_SEI":
        fam = sub[0]
        add({"1": "liso", "3": "cacheado", "4": "crespo"}.get(fam, ""))  # "2" (ondulado) → gap
    else:
        add({"liso": "liso", "cacheado": "cacheado", "crespo": "crespo"}.get(p.curl_type or "", ""))

    # Scalp oiliness
    if p.scalp_oiliness == "alta":
        add("oleoso")
    elif p.scalp_oiliness == "baixa":
        add("seco")
    elif p.scalp_oiliness == "normal":
        add("normal")

    # Dryness / damage along the length
    if p.dryness_damage == "bastante":
        add("seco")
        add("danificado")
    elif p.dryness_damage == "um_pouco":
        add("seco")

    # Chemistry
    treatments = set(p.chemical_treatments or [])
    if treatments:
        add("com_quimica")
    if "coloracao" in treatments:
        add("tingido")
    if "descoloracao" in treatments:
        add("tingido")
        add("danificado")
        add("sensibilizado")
    if "alisamento" in treatments:
        add("com_quimica")
        add("sensibilizado")

    # Thickness (only "fino" exists in the engine)
    if p.thickness == "finos":
        add("fino")

    # Aggressors that push toward damage
    if p.heat_usage in {"diariamente", "3_4_semana"}:
        add("danificado")
    if p.sun_exposure == "alta" or p.water_exposure == "frequente":
        add("danificado")

    return slugs


# Human-readable labels for building Moon's context / greeting
_CURL = {"liso": "liso", "ondulado": "ondulado", "cacheado": "cacheado",
         "crespo": "crespo", "transicao": "em transição capilar"}
_OIL = {"baixa": "couro seco", "normal": "couro normal", "alta": "couro oleoso"}
_DRY = {"nao": "sem ressecamento", "um_pouco": "leve ressecamento", "bastante": "ressecado/danificado"}
_THICK = {"finos": "fios finos", "medios": "fios médios", "grossos": "fios grossos"}
_CHEM = {"coloracao": "coloração", "descoloracao": "descoloração", "alisamento": "alisamento/progressiva"}


def profile_summary(p: HairProfileInput) -> str:
    """One-line natural-language summary for prompts and the chat greeting."""
    parts: list[str] = []
    if p.curl_type:
        label = _CURL.get(p.curl_type, p.curl_type)
        if p.curl_subtype and p.curl_subtype.upper() != "NAO_SEI":
            label += f" {p.curl_subtype.upper()}"
        parts.append(label)
    if p.thickness in _THICK:
        parts.append(_THICK[p.thickness])
    if p.scalp_oiliness in _OIL:
        parts.append(_OIL[p.scalp_oiliness])
    if p.dryness_damage in _DRY and p.dryness_damage != "nao":
        parts.append(_DRY[p.dryness_damage])
    treatments = [_CHEM[t] for t in (p.chemical_treatments or []) if t in _CHEM]
    parts.append(f"química: {', '.join(treatments)}" if treatments else "sem química")
    if p.scalp_issues:
        parts.append("sintomas no couro cabeludo")
    return ", ".join(parts) if parts else "perfil incompleto"
