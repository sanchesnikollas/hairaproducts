# src/extraction/inci_extractor.py
from __future__ import annotations

import re

from src.core.inci_validator import clean_inci_text, validate_inci_list, INCIValidationResult

# Separators used between INCI ingredients across different sites
INCI_SEPARATORS = re.compile(r"[,;●•·|/]\s*|\s{2,}|\n+")

# Matches parentheticals of 4–50 chars that may be bilingual translations
_BILINGUAL_PATTERN = re.compile(r"\s*\([^)]{4,50}?\)")

# INCI-standard parenthetical prefixes that must be preserved
_INCI_PAREN_PREFIXES = ("ci ", "vitamin", "retinol", "tocopherol")


def _strip_bilingual_parens(text: str) -> str:
    """Strip parenthetical translations but keep INCI-standard parens.

    Only removes parentheticals that:
    - are 4–50 chars long
    - contain at least one space (translations are multi-word)
    - do not start with a known INCI prefix (CI, Vitamin, etc.)
    """
    def _should_strip(match: re.Match) -> str:
        inner = match.group(0).strip()[1:-1].strip()  # content inside parens
        # Keep single-word parens like (and)
        if " " not in inner:
            return match.group(0)
        # Keep INCI-standard parentheticals
        if inner.lower().startswith(_INCI_PAREN_PREFIXES):
            return match.group(0)
        # Strip bilingual translation
        return ""

    return _BILINGUAL_PATTERN.sub(_should_strip, text)


def _split_ingredients(text: str) -> list[str]:
    """Split INCI text by common separators (comma, semicolon, bullet, pipe, newline, etc.)."""
    # If newlines are present and yield enough terms, prefer newline split
    if "\n" in text:
        newline_parts = [p.strip() for p in text.split("\n") if p.strip()]
        if len(newline_parts) >= 3:
            return newline_parts
    # If bullets or dots are present, prefer those as the separator
    if "●" in text or "•" in text or "·" in text:
        parts = re.split(r"[●•·]", text)
    # If semicolons are the primary separator (e.g., O Boticário uses pt-BR names with ;)
    elif ";" in text and text.count(";") > text.count(","):
        parts = text.split(";")
    else:
        parts = text.split(",")
    return [p.strip() for p in parts if p.strip()]


def extract_and_validate_inci(
    raw_text: str | None,
    has_section_context: bool = False,
) -> INCIValidationResult:
    if not raw_text or not raw_text.strip():
        return INCIValidationResult(valid=False, rejection_reason="no_inci_text")

    cleaned_text = clean_inci_text(raw_text)
    if not cleaned_text:
        return INCIValidationResult(valid=False, rejection_reason="empty_after_cleaning")

    # Strip bilingual parenthetical translations before splitting/validating.
    # The original raw_text is preserved; only the working copy is modified.
    processing_text = _strip_bilingual_parens(cleaned_text)

    ingredients = _split_ingredients(processing_text)
    return validate_inci_list(ingredients, has_section_context=has_section_context)
