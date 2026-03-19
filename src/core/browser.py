# src/core/browser.py
from __future__ import annotations

import logging
import os
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/125.0.0.0 Safari/537.36'
)


class BrowserClient:
    def __init__(self, delay_seconds: float | None = None, headless: bool = True, use_httpx: bool = False, ssl_verify: bool = True):
        self._delay = delay_seconds or float(os.environ.get("REQUEST_DELAY_SECONDS", "3"))
        self._headless = headless
        self._use_httpx = use_httpx
        self._ssl_verify = ssl_verify
        self._browser = None
        self._page = None
        self._httpx_client = None
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
            self._browser = self._playwright.chromium.launch(
                headless=self._headless,
                args=['--disable-blink-features=AutomationControlled'],
            )
            context = self._browser.new_context(
                user_agent=_DEFAULT_USER_AGENT,
                viewport={'width': 1920, 'height': 1080},
                locale='pt-BR',
            )
            self._page = context.new_page()
            self._page.add_init_script(
                'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            )

    def _ensure_httpx(self):
        if self._httpx_client is None:
            import httpx
            self._httpx_client = httpx.Client(
                headers={
                    'User-Agent': _DEFAULT_USER_AGENT,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                },
                follow_redirects=True,
                timeout=30.0,
                verify=self._ssl_verify,
            )

    def _fetch_page_httpx(self, url: str) -> str:
        """Fetch page HTML using httpx (bypasses WAFs that block headless browsers)."""
        self._ensure_httpx()
        self._rate_limit()
        logger.info(f"Fetching (httpx): {url}")
        resp = self._httpx_client.get(url)
        resp.raise_for_status()
        return resp.text

    def fetch_page(self, url: str, wait_for: str | None = None, expand_accordions: bool = False) -> str:
        if self._use_httpx:
            return self._fetch_page_httpx(url)
        self._ensure_browser()
        self._rate_limit()
        logger.info(f"Fetching: {url}")
        try:
            self._page.goto(url, timeout=45000, wait_until="domcontentloaded")
            self._page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"Navigation issue for {url}: {e}")
            # Browser may have crashed — try to recover
            self._restart_browser()
            try:
                self._page.goto(url, timeout=45000, wait_until="domcontentloaded")
                self._page.wait_for_timeout(2000)
            except Exception as e2:
                logger.warning(f"Retry also failed for {url}: {e2}")
                raise
        if wait_for:
            try:
                self._page.wait_for_selector(wait_for, timeout=5000)
            except Exception:
                logger.debug(f"Selector {wait_for} not found, continuing")
        if expand_accordions:
            self._expand_accordions()
        try:
            return self._page.content()
        except Exception:
            # Page closed between navigation and content read
            self._restart_browser()
            raise

    def _restart_browser(self) -> None:
        """Close and restart the browser (recovers from WAF-induced crashes)."""
        logger.info("Restarting browser...")
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if hasattr(self, '_playwright') and self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._page = None
        time.sleep(2)
        self._ensure_browser()

    def _expand_accordions(self) -> None:
        """Click all accordion/collapsible headers to reveal hidden content."""
        try:
            accordion_selectors = [
                ".accordion-pdp-header",
                "[class*='accordion'] [class*='header']",
                "[class*='collapse'] [class*='trigger']",
                "button[aria-expanded='false']",
            ]
            for selector in accordion_selectors:
                elements = self._page.query_selector_all(selector)
                if elements:
                    for el in elements:
                        try:
                            el.click()
                            self._page.wait_for_timeout(200)
                        except Exception:
                            pass
                    if elements:
                        self._page.wait_for_timeout(500)
                        break
        except Exception as e:
            logger.debug(f"Accordion expansion failed: {e}")

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
        if self._httpx_client:
            self._httpx_client.close()
            self._httpx_client = None
