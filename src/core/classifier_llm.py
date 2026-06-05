"""
Classifier Pass 2 — LLM-grounded classification for dual validation.

Pass 1 (classifier.py) uses keyword/regex heuristics.
Pass 2 (this module) uses Claude to classify the same product independently.
Comparison creates ReviewQueueORM entries for human resolution.

Cheap input — typically just product_name + description + INCI summary,
not the full HTML. Token cost ~500-800 input + ~200 output per product.
"""
from __future__ import annotations

import json
import logging

from src.core.classifier import ClassificationResult
from src.core.llm import LLMClient

logger = logging.getLogger(__name__)


CLASSIFY_PROMPT = """You are classifying a Brazilian hair product into 3 controlled vocabularies.

Return ONLY this JSON object (no prose, no markdown fences):
{
  "function_objective": "<one of: limpar, condicionar, hidratar, nutrir, reconstruir, definir, finalizar, proteger, tratar, modelar, esfoliar, alisar, ondular, colorir, or null>",
  "audience_age": "<one of: under_3, kids, teen, adult>",
  "hair_type": ["array of 0+ from: liso, ondulado, cacheado, crespo, oleoso, seco, misto, normal, com_quimica, tingido, danificado, sensibilizado, fino, grosso"],
  "reasoning": "<one short sentence explaining your choice>"
}

VOCABULARY GUIDE:
- function_objective = the primary action of the product (shampoo→limpar, condicionador→condicionar, máscara→hidratar/nutrir/reconstruir, leave-in/sérum→finalizar, etc.)
- audience_age: under_3 = baby/0-2y, kids = 3-11y, teen = 12-17y, adult = 18+ (default if no age signal)
- hair_type: include ONLY types explicitly mentioned. Multi-valor allowed (e.g. ["seco", "danificado"]). If product is generic/all-types, return [].

CRITICAL: NEVER hallucinate. If the product description doesn't mention a hair type, return [] for hair_type. Default audience_age to "adult" only when no kid/teen/baby signals exist."""


def classify_with_llm(
    product_name: str | None,
    description: str | None,
    inci_ingredients: list[str] | None,
    product_category: str | None,
    llm: LLMClient,
) -> ClassificationResult | None:
    """Run Pass 2 LLM classification.

    Returns ClassificationResult with method='llm' or None on error.
    """
    if not llm.can_call:
        return None

    # Build compact context (no HTML, just structured fields)
    parts = []
    if product_name:
        parts.append(f"Product name: {product_name}")
    if product_category:
        parts.append(f"Category: {product_category}")
    if description:
        parts.append(f"Description: {description[:1500]}")
    if inci_ingredients and isinstance(inci_ingredients, list):
        parts.append(f"INCI (first 15): {', '.join(inci_ingredients[:15])}")
    page_text = "\n".join(parts)

    if not page_text.strip():
        return None

    try:
        result = llm.extract_structured(page_text=page_text, prompt=CLASSIFY_PROMPT, max_tokens=512)
    except Exception as e:
        logger.warning(f"Classifier LLM failed for {product_name}: {e}")
        return None

    if not isinstance(result, dict):
        return None

    # Validate enum membership (defensive — LLM might invent values)
    valid_functions = {"limpar", "condicionar", "hidratar", "nutrir", "reconstruir", "definir",
                       "finalizar", "proteger", "tratar", "modelar", "esfoliar", "alisar", "ondular", "colorir"}
    valid_ages = {"under_3", "kids", "teen", "adult"}
    valid_hair_types = {"liso", "ondulado", "cacheado", "crespo", "oleoso", "seco", "misto", "normal",
                        "com_quimica", "tingido", "danificado", "sensibilizado", "fino", "grosso"}

    func = result.get("function_objective")
    if func not in valid_functions:
        func = None

    age = result.get("audience_age", "adult")
    if age not in valid_ages:
        age = "adult"

    hair_types = result.get("hair_type") or []
    if isinstance(hair_types, str):
        hair_types = [hair_types]
    hair_types = [ht for ht in hair_types if ht in valid_hair_types]

    return ClassificationResult(
        hair_type=hair_types if hair_types else None,
        audience_age=age,
        function_objective=func,
        confidence_per_field={
            "function_objective": 0.85 if func else 0.0,
            "audience_age": 0.85,
            "hair_type": 0.85 if hair_types else 0.5,
        },
        method="llm",
        matched_keywords={
            "reasoning": [result.get("reasoning", "")],
        },
    )
