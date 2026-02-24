# src/extraction/inci_extractor.py
from __future__ import annotations

from src.core.inci_validator import clean_inci_text, validate_inci_list, INCIValidationResult


def extract_and_validate_inci(raw_text: str | None) -> INCIValidationResult:
    if not raw_text or not raw_text.strip():
        return INCIValidationResult(valid=False, rejection_reason="no_inci_text")

    cleaned_text = clean_inci_text(raw_text)
    if not cleaned_text:
        return INCIValidationResult(valid=False, rejection_reason="empty_after_cleaning")

    ingredients = [i.strip() for i in cleaned_text.split(",") if i.strip()]
    return validate_inci_list(ingredients)
