# src/core/browser.py
from __future__ import annotations

import logging
import os
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class BrowserClient:
    def __init__(self, delay_seconds: float | None = None, headless: bool = True):
        self._delay = delay_seconds or float(os.environ.get("REQUEST_DELAY_SECONDS", "3"))
        self._headless = headless
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
        try:
            self._page.goto(url, timeout=45000, wait_until="domcontentloaded")
            self._page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"Navigation issue for {url}: {e}")
        if wait_for:
            try:
                self._page.wait_for_selector(wait_for, timeout=5000)
            except Exception:
                logger.debug(f"Selector {wait_for} not found, continuing")
        return self._page.content()

    def fetch_page_text(self, url: str) -> str:
        self._ensure_browser()
        self._rate_limit()
        try:
            self._page.goto(url, timeout=45000, wait_until="domcontentloaded")
            self._page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"Navigation issue for {url}: {e}")
        return self._page.inner_text("body")

    def get_links(self, url: str, allowed_domains: list[str] | None = None) -> list[str]:
        """Fetch a page and extract all links, optionally filtered by domain."""
        self._ensure_browser()
        self._rate_limit()
        try:
            self._page.goto(url, timeout=45000, wait_until="domcontentloaded")
            self._page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"Navigation issue for {url}: {e}")
            return []
        links = self._page.eval_on_selector_all('a[href]', 'els => els.map(e => e.href)')
        if allowed_domains:
            links = [l for l in links if self.is_allowed_domain(l, allowed_domains)]
        return list(set(links))

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
