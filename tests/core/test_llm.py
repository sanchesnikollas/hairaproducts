# tests/core/test_llm.py
import pytest
from unittest.mock import MagicMock, patch
from src.core.llm import LLMClient


class TestLLMClient:
    def test_budget_check(self):
        client = LLMClient(max_calls_per_brand=2)
        client.reset_brand_budget()
        assert client.can_call is True

    def test_budget_exceeded_raises(self):
        client = LLMClient(max_calls_per_brand=0)
        client.reset_brand_budget()
        with pytest.raises(RuntimeError, match="budget"):
            client.extract_structured(page_text="test", prompt="test")
