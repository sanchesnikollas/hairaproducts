from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

PRODUCT_TYPES = {
    "shampoo": ["shampoo"],
    "condicionador": ["condicionador", "conditioner"],
    "mascara": ["mascara", "máscara", "mask", "masque"],
    "leave-in": ["leave-in", "leave in"],
    "creme": ["creme de pentear", "creme para pentear", "creme pentear"],
    "oleo": ["oleo", "óleo", "oil"],
    "spray": ["spray"],
    "serum": ["serum", "sérum"],
    "ampola": ["ampola", "ampoule"],
    "kit": ["kit"],
    "gel": ["gel", "gelatina", "geleia"],
    "finalizador": ["finalizador"],
}


def normalize_name(name: str) -> str:
    name = name.lower()
    name = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    )
    name = re.sub(r"\b\d+[.,]?\d*\s*(ml|g|kg|l|oz|lt)\b", "", name)
    name = re.sub(r"\s*[-/]\s*(un|und|unid)\b", "", name)
    name = re.sub(r"\s*kit\s+com\s+\d+", "kit", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def detect_product_type(name: str) -> str | None:
    lower = name.lower()
    for ptype, keywords in PRODUCT_TYPES.items():
        for kw in keywords:
            if kw in lower:
                return ptype
    return None


def match_products(
    product_name: str,
    product_brand: str,
    candidates: list[dict],
    auto_threshold: float = 0.90,
    review_threshold: float = 0.75,
) -> list[dict]:
    norm_name = normalize_name(product_name)
    product_type = detect_product_type(product_name)

    matches = []
    for cand in candidates:
        if not cand.get("inci_ingredients"):
            continue

        cand_norm = normalize_name(cand["product_name"] or "")
        seq_ratio = SequenceMatcher(None, norm_name, cand_norm).ratio()
        norm_sorted = " ".join(sorted(norm_name.split()))
        cand_sorted = " ".join(sorted(cand_norm.split()))
        token_ratio = SequenceMatcher(None, norm_sorted, cand_sorted).ratio()
        ratio = max(seq_ratio, token_ratio)

        if ratio < review_threshold:
            continue

        cand_type = detect_product_type(cand["product_name"] or "")
        type_match = (
            product_type is None
            or cand_type is None
            or product_type == cand_type
        )

        if ratio > auto_threshold and type_match:
            action = "auto_apply"
        else:
            action = "review"

        matches.append({
            "external_id": cand["id"],
            "source": cand["source"],
            "source_url": cand.get("source_url", ""),
            "score": ratio,
            "action": action,
            "type_match": type_match,
            "cand_name": cand["product_name"],
            "inci_ingredients": cand["inci_ingredients"],
        })

    matches.sort(key=lambda m: (-m["score"], m["source"] != "belezanaweb"))
    return matches[:1]
