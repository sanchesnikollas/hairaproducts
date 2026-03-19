# src/core/taxonomy.py
from __future__ import annotations

import re

HAIR_PRODUCT_TYPES: set[str] = {
    "shampoo",
    "conditioner",
    "mask",
    "treatment",
    "leave_in",
    "oil_serum",
    "tonic",
    "exfoliant",
    "scalp_treatment",
    "gel",
    "mousse",
    "spray",
    "pomade",
    "wax",
    "clay",
    "paste",
    "texturizer",
    "finisher",
    "ampule",
    "serum",
    "cream",
    "coloracao",
    "oxidante",
    "descolorante",
    "relaxante",
    "ativador",
    "protetor",
    "reconstructor",
    "reparador",
    "kit",
}

HAIR_KEYWORDS: list[str] = [
    "shampoo", "condicionador", "conditioner", "máscara capilar", "mascara capilar",
    "hair mask", "tratamento capilar", "leave-in", "leave in", "óleo capilar",
    "oil hair", "tônico capilar", "tonico capilar", "scalp", "couro cabeludo",
    "antiqueda", "anti-queda", "queda capilar", "crescimento capilar",
    "cabelo", "cabelos", "hair", "capilar", "fios",
    "gel fixador", "mousse", "spray fixador", "pomada", "cera capilar",
    "wax", "clay", "pasta modeladora", "texturizador", "finalizador",
    "ampola", "sérum capilar", "serum capilar", "creme para pentear",
    "creme de pentear", "alisamento", "progressiva", "reconstrução",
    "hidratação capilar", "nutrição capilar", "reparação",
]

EXCLUDE_KEYWORDS: list[str] = [
    "corpo", "corporal", "body", "facial", "face", "rosto",
    "maquiagem", "makeup", "perfume", "fragrance", "fragrância",
    "unhas", "nail", "acessório", "accessory",
    "protetor solar", "sunscreen", "desodorante", "deodorant",
    "sabonete líquido", "sabonete corporal",
    "hidratante corporal", "body lotion", "body cream",
    "batom", "lipstick", "rímel", "mascara para cílios",
]

KIT_PATTERNS: list[str] = [
    r"/kit[-_]", r"/combo[-_]", r"/bundle[-_]", r"/set[-_]",
    r"/kit/", r"/combo/", r"/bundle/",
]

MALE_TARGETING_KEYWORDS: list[str] = [
    "masculino", "masculina", "men", "for men", "man",
    "barber", "barbearia",
]

KIDS_KEYWORDS: list[str] = [
    "kids", "infantil", "criança", "children", "baby",
]

_TYPE_MAP: list[tuple[list[str], str]] = [
    # --- Coloração / química (must come before generic matches) ---
    (["água oxigenada", "agua oxigenada", "oxidante", "ox "], "oxidante"),
    (["pó descolorante", "po descolorante", "descolorante"], "descolorante"),
    (["coloração", "coloracao", "tintura", "tonalizante", "color intensy", "color delicaté", "color delicate", "magnific color"], "coloracao"),
    (["relaxante", "relaxamento", "alisante", "guanidina"], "relaxante"),
    # --- Tratamento / reconstrução ---
    (["queratina líquida", "queratina liquida", "proteína capilar", "proteina capilar", "repositor de massa", "rmc system"], "reconstructor"),
    (["reconstrutor", "reconstrução", "reconstrutora", "overnight"], "reconstructor"),
    (["reparador de pontas", "reparador"], "reparador"),
    (["ativador de cachos", "ativador"], "ativador"),
    (["filtro solar", "defesa solar", "protetor da cor", "blindagem"], "protetor"),
    # --- Básicos ---
    (["shampoo", "xampu"], "shampoo"),
    (["condicionador", "conditioner"], "conditioner"),
    (["máscara", "mascara", "mask"], "mask"),
    (["leave-in", "leave in"], "leave_in"),
    (["creme de pentear", "creme para pentear"], "cream"),
    (["óleo", "oleo", "oil"], "oil_serum"),
    (["sérum", "serum"], "oil_serum"),
    (["tônico", "tonico", "tonic"], "tonic"),
    (["pomada", "pomade"], "pomade"),
    (["gel"], "gel"),
    (["mousse"], "mousse"),
    (["spray", "hair spray"], "spray"),
    (["cera", "wax"], "wax"),
    (["argila", "clay"], "clay"),
    (["pasta", "paste"], "paste"),
    (["ampola", "ampule"], "ampule"),
    (["finalizador", "finisher"], "finisher"),
    (["modelador", "modeladora"], "finisher"),
    (["fluido", "fluído"], "finisher"),
    (["seca sem frizz", "antifrizz"], "finisher"),
    # --- Cremes genéricos (catch-all, must be after creme de pentear) ---
    (["creme disciplinante", "creme nutritivo", "creme protetor", "creme reconstrutor"], "cream"),
    (["cream", "creme"], "cream"),
    (["tratamento", "treatment"], "treatment"),
    (["esfoliante", "exfoliant"], "exfoliant"),
    (["texturizador", "texturizer"], "texturizer"),
    (["emulsão neutralizante", "neutralizante"], "relaxante"),
    (["renovador capilar"], "treatment"),
]


CATEGORY_MAP: dict[str, str] = {
    "shampoo": "shampoo",
    "conditioner": "condicionador",
    "mask": "mascara",
    "treatment": "tratamento",
    "ampule": "tratamento",
    "scalp_treatment": "tratamento",
    "exfoliant": "tratamento",
    "tonic": "tratamento",
    "reconstructor": "tratamento",
    "reparador": "tratamento",
    "protetor": "tratamento",
    "leave_in": "leave_in",
    "cream": "leave_in",
    "ativador": "leave_in",
    "oil_serum": "oleo_serum",
    "serum": "oleo_serum",
    "gel": "styling",
    "mousse": "styling",
    "spray": "styling",
    "pomade": "styling",
    "wax": "styling",
    "clay": "styling",
    "paste": "styling",
    "texturizer": "styling",
    "finisher": "styling",
    "coloracao": "coloracao",
    "oxidante": "coloracao",
    "descolorante": "coloracao",
    "relaxante": "transformacao",
    "kit": "kit",
}

VALID_CATEGORIES: set[str] = {
    "shampoo", "condicionador", "mascara", "tratamento",
    "leave_in", "oleo_serum", "styling", "coloracao",
    "transformacao", "kit",
}

_COLORACAO_KEYWORDS: list[str] = [
    "coloração", "coloracao", "tintura", "tonalizante",
    "matizador", "matizadora", "oxidante", "ox ",
    "descolorante", "decolorante", "pó descolorante",
]


def normalize_category(product_type_normalized: str | None, product_name: str = "") -> str | None:
    """Map a normalized product type to a high-level category."""
    # Check coloração keywords first (product_type_normalized may be None for these)
    name_lower = product_name.lower()
    for kw in _COLORACAO_KEYWORDS:
        if kw in name_lower:
            return "coloracao"

    if not product_type_normalized:
        return None
    return CATEGORY_MAP.get(product_type_normalized)


def normalize_product_type(raw_name: str) -> str | None:
    lower = raw_name.lower()
    for keywords, normalized in _TYPE_MAP:
        for kw in keywords:
            if kw in lower:
                return normalized
    return None


def detect_gender_target(product_name: str, url: str) -> str:
    combined = f"{product_name} {url}".lower()
    if "unissex" in combined or "unisex" in combined:
        return "unisex"
    for kw in KIDS_KEYWORDS:
        if kw in combined:
            return "kids"
    for kw in MALE_TARGETING_KEYWORDS:
        if kw in combined:
            return "men"
    return "unknown"


def is_hair_relevant_by_keywords(
    product_name: str, url: str, description: str = ""
) -> tuple[bool, str]:
    combined = f"{product_name} {url} {description}".lower()
    for ekw in EXCLUDE_KEYWORDS:
        if ekw in combined:
            return False, ""
    for hkw in HAIR_KEYWORDS:
        if hkw in combined:
            return True, f"keyword '{hkw}' found"
    return False, ""


def is_kit_url(url: str) -> bool:
    lower_url = url.lower()
    for pattern in KIT_PATTERNS:
        if re.search(pattern, lower_url):
            return True
    return False
