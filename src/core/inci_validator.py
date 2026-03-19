# src/core/inci_validator.py
from __future__ import annotations

import re
from dataclasses import dataclass, field

CUT_MARKERS: list[str] = [
    "modo de uso", "como usar", "how to use", "directions",
    "benefícios", "benefits", "indicação", "precauções", "warnings",
    "validade", "reg. ms", "sac:", "cnpj", "fabricante",
]

GARBAGE_PHRASES: list[str] = [
    "click here", "see more", "read more", "ver mais", "clique aqui",
    "saiba mais", "leia mais", "show more", "infamous", "known for",
    "commonly used", "is a type of", "can cause", "compare",
    "report error", "embed",
]

VERB_INDICATORS: list[str] = [
    "aplique", "aplicar", "massageie", "enxágue", "enxague",
    "use", "apply", "massage", "rinse", "wash", "lavar",
    "espalhe", "distribua", "deixe agir", "aguarde",
]

PRODUCT_HEADING_PATTERNS: list[str] = [
    r"shampoo\s*:", r"condicionador\s*:", r"conditioner\s*:",
    r"máscara\s*:", r"mascara\s*:", r"mask\s*:",
    r"creme\s*:", r"leave-in\s*:", r"óleo\s*:",
]


@dataclass
class INCIValidationResult:
    valid: bool
    cleaned: list[str] = field(default_factory=list)
    rejection_reason: str = ""
    removed: list[str] = field(default_factory=list)


def clean_inci_text(raw: str) -> str:
    text = raw
    lower = text.lower()
    for marker in CUT_MARKERS:
        idx = lower.find(marker)
        if idx != -1:
            text = text[:idx]
            lower = text.lower()
    for phrase in GARBAGE_PHRASES:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    return text.strip()


def validate_ingredient(ingredient: str) -> bool:
    s = ingredient.strip()
    if len(s) < 2 or len(s) > 80:
        return False
    if re.search(r"https?://", s, re.IGNORECASE):
        return False
    if len(s.split()) > 8:
        return False
    lower = s.lower()
    for verb in VERB_INDICATORS:
        if verb in lower and len(s.split()) > 3:
            return False
    return True


def detect_concatenation(ingredients: list[str]) -> bool:
    lower_list = [i.lower().strip() for i in ingredients]
    aqua_positions = [i for i, item in enumerate(lower_list) if item in ("aqua", "water", "aqua/water")]
    if len(aqua_positions) >= 2:
        for j in range(1, len(aqua_positions)):
            if aqua_positions[j] - aqua_positions[j - 1] > 1:
                return True
    for item in lower_list:
        for pattern in PRODUCT_HEADING_PATTERNS:
            if re.match(pattern, item):
                return True
    return False


def detect_repetition(ingredients: list[str]) -> bool:
    normalized = [i.lower().strip() for i in ingredients]
    n = len(normalized)
    for block_size in range(3, n // 2 + 1):
        block = normalized[:block_size]
        next_block = normalized[block_size : block_size * 2]
        if block == next_block:
            return True
    return False


def validate_inci_list(ingredients: list[str]) -> INCIValidationResult:
    if detect_repetition(ingredients):
        return INCIValidationResult(
            valid=False, rejection_reason="repetition_detected"
        )
    if detect_concatenation(ingredients):
        return INCIValidationResult(
            valid=False, rejection_reason="concat_detected"
        )
    seen: set[str] = set()
    cleaned: list[str] = []
    removed: list[str] = []
    for ing in ingredients:
        s = ing.strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            removed.append(s)
            continue
        if not validate_ingredient(s):
            removed.append(s)
            continue
        seen.add(key)
        cleaned.append(s)
    if len(cleaned) < 5:
        return INCIValidationResult(
            valid=False,
            cleaned=cleaned,
            removed=removed,
            rejection_reason="min_ingredients: only {} valid terms".format(len(cleaned)),
        )
    return INCIValidationResult(valid=True, cleaned=cleaned, removed=removed)
