# src/extraction/inci_extractor.py
from __future__ import annotations

import re

from src.core.inci_validator import clean_inci_text, validate_inci_list, INCIValidationResult

# Separators used between INCI ingredients across different sites
INCI_SEPARATORS = re.compile(r"[,●•·|/]\s*|\s{2,}")


def _split_ingredients(text: str) -> list[str]:
    """Split INCI text by common separators (comma, bullet, pipe, etc.)."""
    # If bullets or dots are present, prefer those as the separator
    if "●" in text or "•" in text or "·" in text:
        parts = re.split(r"[●•·]", text)
    else:
        parts = text.split(",")
    return [p.strip() for p in parts if p.strip()]


def extract_and_validate_inci(raw_text: str | None) -> INCIValidationResult:
    if not raw_text or not raw_text.strip():
        return INCIValidationResult(valid=False, rejection_reason="no_inci_text")

    cleaned_text = clean_inci_text(raw_text)
    if not cleaned_text:
        return INCIValidationResult(valid=False, rejection_reason="empty_after_cleaning")

    ingredients = _split_ingredients(cleaned_text)
    return validate_inci_list(ingredients)
