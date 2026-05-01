"""
Pass 2 — LLM grounded re-extraction for dual validation.

Strategy:
  - Pass 1 (deterministic): extract_product_deterministic uses JSON-LD + CSS selectors
  - Pass 2 (this module): give the same HTML to Claude with a structured prompt;
    LLM must extract the same fields independently
  - dual_validator.compare_fields confronts both passes
  - Divergences -> ReviewQueueORM (human resolution)

LLM is instructed to NEVER hallucinate — only return values present in the page.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from src.core.llm import LLMClient

logger = logging.getLogger(__name__)


# Strip HTML to text (lossy but enough for LLM context)
def html_to_text(html: str, max_chars: int = 14000) -> str:
    """Convert HTML to text, prioritizing visible content."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback: regex strip tags
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]

    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()

    # Prefer main content sections
    main = soup.find("main") or soup.find("article") or soup.find("body") or soup
    text = main.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


PASS2_PROMPT = """Extract product information from the hair product page text below.

Return ONLY a single JSON object with these fields. Use null for any field NOT explicitly present in the text:

{
  "product_name": "exact product name as shown on the page",
  "price": numeric price in BRL (only the number, e.g. 89.90) or null,
  "currency": "BRL" or other ISO 4217 code or null,
  "description": "short product description (1-3 sentences max), use null if no clear description",
  "composition": "free-text composition section if present (e.g. 'Composição: ...')",
  "care_usage": "usage/application instructions if present (e.g. 'Modo de uso: aplique...')",
  "size_volume": "size like '300ml', '250g', '1L' if present",
  "inci_ingredients": ["array", "of", "INCI", "ingredients"] or null,
  "benefits_claims": ["array of benefit claims/bullets"] or null,
  "line_collection": "product line/collection name if mentioned (e.g. 'Resistance', 'Nutritive')"
}

CRITICAL RULES:
- NEVER hallucinate. If a field is not clearly stated, use null.
- For inci_ingredients: include only when you see a clear ingredient list (separated by commas/bullets, with chemistry-like names like Aqua, Cetearyl Alcohol, Sodium Laureth Sulfate, etc.). Do NOT confuse with composition or marketing text.
- Return ONLY the JSON object, no prose, no markdown fences."""


def extract_pass2_llm(html: str, url: str, llm: LLMClient) -> dict[str, Any]:
    """Run Pass 2 LLM-grounded extraction on HTML.

    Returns dict with same field names as Pass 1 (extract_product_deterministic).
    Returns empty dict on LLM error or parse failure.
    """
    if not llm.can_call:
        logger.warning("LLM budget exhausted, skipping Pass 2")
        return {}

    page_text = html_to_text(html)
    if not page_text or len(page_text) < 100:
        logger.warning(f"Page text too short for Pass 2: {url}")
        return {}

    try:
        result = llm.extract_structured(page_text=page_text, prompt=PASS2_PROMPT, max_tokens=2048)
    except Exception as e:
        logger.warning(f"Pass 2 LLM failed for {url}: {e}")
        return {}

    if not isinstance(result, dict):
        logger.warning(f"Pass 2 returned non-dict: {url}")
        return {}

    # Normalize types — Claude may return strings for numbers
    if "price" in result and isinstance(result["price"], str):
        try:
            result["price"] = float(re.sub(r"[^\d.,]", "", result["price"]).replace(",", "."))
        except ValueError:
            result["price"] = None

    return result
