from __future__ import annotations

import src.core.firecrawl_client as fc
from src.core.browser import BrowserClient


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class TestFirecrawlClient:
    def test_unavailable_without_key(self, monkeypatch):
        monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
        assert fc.firecrawl_available() is False
        assert fc.firecrawl_fetch_html("https://x.com") is None

    def test_available_with_key(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        assert fc.firecrawl_available() is True

    def test_returns_html_on_success(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        import httpx
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResp({"data": {"html": "<html>ok</html>"}}))
        assert fc.firecrawl_fetch_html("https://x.com") == "<html>ok</html>"

    def test_none_on_empty_payload(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        import httpx
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResp({"data": {}}))
        assert fc.firecrawl_fetch_html("https://x.com") is None

    def test_never_raises_on_error(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        import httpx

        def boom(*a, **k):
            raise httpx.ConnectError("down")

        monkeypatch.setattr(httpx, "post", boom)
        assert fc.firecrawl_fetch_html("https://x.com") is None


class TestBrowserFirecrawlFallback:
    def test_native_error_falls_back_to_firecrawl(self, monkeypatch):
        b = BrowserClient(use_httpx=True)
        monkeypatch.setattr(b, "_fetch_page_native", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("blocked")))
        monkeypatch.setattr("src.core.firecrawl_client.firecrawl_available", lambda: True)
        monkeypatch.setattr("src.core.firecrawl_client.firecrawl_fetch_html", lambda url, **k: "<html>fc</html>")
        assert b.fetch_page("https://x.com") == "<html>fc</html>"

    def test_native_error_reraises_without_key(self, monkeypatch):
        b = BrowserClient(use_httpx=True)
        monkeypatch.setattr(b, "_fetch_page_native", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("blocked")))
        monkeypatch.setattr("src.core.firecrawl_client.firecrawl_available", lambda: False)
        try:
            b.fetch_page("https://x.com")
            assert False, "should have re-raised"
        except RuntimeError:
            pass

    def test_short_page_falls_back(self, monkeypatch):
        b = BrowserClient(use_httpx=True)
        monkeypatch.setattr(b, "_fetch_page_native", lambda *a, **k: "tiny")
        monkeypatch.setattr("src.core.firecrawl_client.firecrawl_available", lambda: True)
        monkeypatch.setattr("src.core.firecrawl_client.firecrawl_fetch_html", lambda url, **k: "<html>" + "x" * 300 + "</html>")
        assert b.fetch_page("https://x.com").startswith("<html>")

    def test_good_native_page_no_fallback(self, monkeypatch):
        b = BrowserClient(use_httpx=True)
        big = "<html>" + "y" * 500 + "</html>"
        monkeypatch.setattr(b, "_fetch_page_native", lambda *a, **k: big)
        # firecrawl should never be called; make it explode if it is
        monkeypatch.setattr("src.core.firecrawl_client.firecrawl_available", lambda: (_ for _ in ()).throw(AssertionError("called")))
        assert b.fetch_page("https://x.com") == big
