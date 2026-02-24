# src/core/llm.py
from __future__ import annotations

import json
import logging
import os

import anthropic

from src.pipeline.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, max_calls_per_brand: int | None = None):
        self._model = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else None
        max_calls = max_calls_per_brand if max_calls_per_brand is not None else int(os.environ.get("MAX_LLM_CALLS_PER_BRAND", "50"))
        self._tracker = CostTracker(max_calls=max_calls)

    @property
    def can_call(self) -> bool:
        return self._tracker.can_call

    @property
    def cost_summary(self) -> dict:
        return self._tracker.summary()

    def reset_brand_budget(self) -> None:
        self._tracker = CostTracker(max_calls=self._tracker.max_calls)

    def extract_structured(self, page_text: str, prompt: str, max_tokens: int = 4096) -> dict:
        if not self._tracker.can_call:
            raise RuntimeError("LLM budget exceeded for this brand")
        if not self._client:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        system = (
            "You are a hair product data extractor. Extract ONLY information present "
            "in the provided page text. If a field is not found, return null. "
            "Never hallucinate or infer data not explicitly present."
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": f"{prompt}\n\n---PAGE TEXT---\n{page_text[:15000]}"}],
        )
        self._tracker.record_call(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        text = response.content[0].text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```json" in text:
                start = text.index("```json") + 7
                end = text.index("```", start)
                return json.loads(text[start:end])
            elif "```" in text:
                start = text.index("```") + 3
                end = text.index("```", start)
                return json.loads(text[start:end])
            logger.warning("LLM response was not valid JSON")
            return {}

    def classify_hair_relevance(self, product_name: str, page_snippet: str) -> dict:
        prompt = (
            "Based ONLY on the product name and page text below, determine if this is a hair/scalp product.\n"
            "Return JSON: {\"hair_related\": true/false, \"reason\": \"...\", \"evidence_quote\": \"...\"}\n\n"
            f"Product name: {product_name}\n"
        )
        return self.extract_structured(page_text=page_snippet, prompt=prompt, max_tokens=256)
