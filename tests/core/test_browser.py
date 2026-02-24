# tests/core/test_browser.py
import pytest
from unittest.mock import MagicMock, patch
from src.core.browser import BrowserClient


class TestBrowserClient:
    def test_rate_limiting_config(self):
        client = BrowserClient(delay_seconds=5)
        assert client._delay == 5

    def test_default_delay(self):
        client = BrowserClient()
        assert client._delay == 3

    def test_respects_domain_allowlist(self):
        client = BrowserClient()
        assert client.is_allowed_domain("https://www.amend.com.br/produto", ["www.amend.com.br"]) is True
        assert client.is_allowed_domain("https://www.incidecoder.com/x", ["www.amend.com.br"]) is False
