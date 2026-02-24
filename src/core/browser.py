# src/core/browser.py
from __future__ import annotations

import logging
import os
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class BrowserClient:
    def __init__(self, delay_seconds: float | None = None):
        self._delay = delay_seconds or float(os.environ.get("REQUEST_DELAY_SECONDS", "3"))
        self._headless = os.environ.get("HEADLESS", "true").lower() == "true"
        self._browser = None
        self._page = None
        self._last_request_time: float = 0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_request_time = time.time()

    def _ensure_browser(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self._headless)
            self._page = self._browser.new_page()

    def fetch_page(self, url: str, wait_for: str | None = None) -> str:
        self._ensure_browser()
        self._rate_limit()
        logger.info(f"Fetching: {url}")
        self._page.goto(url, timeout=30000, wait_until="networkidle")
        if wait_for:
            try:
                self._page.wait_for_selector(wait_for, timeout=5000)
            except Exception:
                logger.debug(f"Selector {wait_for} not found, continuing")
        return self._page.content()

    def fetch_page_text(self, url: str) -> str:
        self._ensure_browser()
        self._rate_limit()
        self._page.goto(url, timeout=30000, wait_until="networkidle")
        return self._page.inner_text("body")

    @staticmethod
    def is_allowed_domain(url: str, allowed_domains: list[str]) -> bool:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return any(host == d or host.endswith(f".{d}") for d in allowed_domains)

    def close(self) -> None:
        if self._browser:
            self._browser.close()
            self._playwright.stop()
            self._browser = None
            self._page = None
