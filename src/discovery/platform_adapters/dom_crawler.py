# src/discovery/platform_adapters/dom_crawler.py
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from src.core.models import DiscoveredURL
from src.discovery.platform_adapters.base import BaseAdapter
from src.discovery.url_classifier import classify_url, URLType

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class DOMCrawlerAdapter(BaseAdapter):
    name = "dom_crawler"

    def __init__(self, browser=None, max_depth: int = 2):
        self._browser = browser
        self._max_depth = max_depth

    def _extract_links_from_html(self, html: str, base_url: str, allowed_domains: list[str]) -> list[str]:
        if BeautifulSoup is None:
            return []
        soup = BeautifulSoup(html, "lxml")
        links = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            host = parsed.hostname or ""
            if any(host == d or host.endswith(f".{d}") for d in allowed_domains):
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"
                links.add(clean_url)
        return list(links)

    def _extract_links_via_browser(self, url: str, allowed_domains: list[str]) -> list[str]:
        """Use browser's get_links if available, else fetch HTML and parse."""
        if hasattr(self._browser, 'get_links'):
            return self._browser.get_links(url, allowed_domains)
        html = self._browser.fetch_page(url)
        return self._extract_links_from_html(html, url, allowed_domains)

    def discover(self, config: dict) -> list[DiscoveredURL]:
        entrypoints = config.get("entrypoints", [])
        allowed_domains = config.get("allowed_domains", [])
        max_pages = config.get("max_pages", 500)
        product_url_pattern = config.get("product_url_pattern")

        if not self._browser:
            for ep_url in entrypoints:
                logger.warning(f"No browser configured, skipping DOM crawl of {ep_url}")
            return []

        all_urls: set[str] = set()
        visited: set[str] = set()
        to_crawl: list[tuple[str, int]] = [(ep, 0) for ep in entrypoints]

        while to_crawl and len(all_urls) < max_pages:
            url, depth = to_crawl.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                links = self._extract_links_via_browser(url, allowed_domains)
                logger.info(f"Crawled {len(links)} links from {url} (depth={depth})")
                all_urls.update(links)

                # Queue category pages for deeper crawl
                if depth < self._max_depth:
                    for link in links:
                        if link not in visited:
                            link_type = classify_url(link, product_url_pattern)
                            if link_type == URLType.CATEGORY:
                                to_crawl.append((link, depth + 1))
            except Exception as e:
                logger.warning(f"Failed to crawl {url}: {e}")

        discovered: list[DiscoveredURL] = []
        for url in list(all_urls)[:max_pages]:
            url_type = classify_url(url, product_url_pattern)
            discovered.append(DiscoveredURL(
                url=url,
                source_type="dom_crawl",
                hair_relevant=url_type in (URLType.PRODUCT, URLType.CATEGORY),
                hair_relevance_reason=f"url_type={url_type.value}",
                is_kit=url_type == URLType.KIT,
            ))

        return discovered
