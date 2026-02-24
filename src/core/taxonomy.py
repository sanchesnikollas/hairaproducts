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
    (["shampoo"], "shampoo"),
    (["condicionador", "conditioner"], "conditioner"),
    (["máscara", "mascara", "mask"], "mask"),
    (["leave-in", "leave in"], "leave_in"),
    (["óleo", "oleo", "oil"], "oil_serum"),
    (["sérum", "serum"], "oil_serum"),
    (["tônico", "tonico", "tonic"], "tonic"),
    (["pomada", "pomade"], "pomade"),
    (["gel"], "gel"),
    (["mousse"], "mousse"),
    (["spray"], "spray"),
    (["cera", "wax"], "wax"),
    (["argila", "clay"], "clay"),
    (["pasta", "paste"], "paste"),
    (["creme de pentear", "creme para pentear", "cream"], "cream"),
    (["ampola", "ampule"], "ampule"),
    (["finalizador", "finisher"], "finisher"),
    (["tratamento", "treatment", "reconstrução"], "treatment"),
    (["esfoliante", "exfoliant"], "exfoliant"),
    (["texturizador", "texturizer"], "texturizer"),
]


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
