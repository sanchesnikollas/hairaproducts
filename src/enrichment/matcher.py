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


def normalize_name(name: str, strip_brand: str | None = None) -> str:
    name = name.lower()
    name = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    )
    name = re.sub(r"\b\d+[.,]?\d*\s*(ml|g|kg|l|oz|lt)\b", "", name)
    name = re.sub(r"\s*[-/]\s*(un|und|unid)\b", "", name)
    name = re.sub(r"\s*kit\s+com\s+\d+", "kit", name)

    if strip_brand:
        brand_norm = "".join(
            c for c in unicodedata.normalize("NFD", strip_brand.lower())
            if unicodedata.category(c) != "Mn"
        )
        # Remove brand as standalone word, possibly hyphenated; also handles "X-Brand"
        name = re.sub(rf"\b{re.escape(brand_norm)}\b", "", name)
        # Common variations: bio extratus, bioextratus, bio-extratus
        flat = brand_norm.replace("-", "").replace(" ", "")
        if flat != brand_norm:
            name = re.sub(rf"\b{re.escape(flat)}\b", "", name)

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
    norm_name_stripped = normalize_name(product_name, strip_brand=product_brand)
    product_type = detect_product_type(product_name)

    matches = []
    for cand in candidates:
        if not cand.get("inci_ingredients"):
            continue

        cand_raw = cand["product_name"] or ""
        cand_norm = normalize_name(cand_raw)
        cand_norm_stripped = normalize_name(cand_raw, strip_brand=product_brand)

        # Compare across 4 variants and take best ratio
        ratios = []
        for left, right in (
            (norm_name, cand_norm),
            (norm_name_stripped, cand_norm_stripped),
            (norm_name, cand_norm_stripped),
            (norm_name_stripped, cand_norm),
        ):
            if not left or not right:
                continue
            seq_ratio = SequenceMatcher(None, left, right).ratio()
            l_sorted = " ".join(sorted(left.split()))
            r_sorted = " ".join(sorted(right.split()))
            tok_ratio = SequenceMatcher(None, l_sorted, r_sorted).ratio()
            ratios.append(max(seq_ratio, tok_ratio))
        ratio = max(ratios) if ratios else 0.0

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
