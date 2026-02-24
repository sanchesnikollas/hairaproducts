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

    def __init__(self, browser=None):
        self._browser = browser

    def _extract_links(self, html: str, base_url: str, allowed_domains: list[str]) -> list[str]:
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
                links.add(clean_url)
        return list(links)

    def discover(self, config: dict) -> list[DiscoveredURL]:
        entrypoints = config.get("entrypoints", [])
        allowed_domains = config.get("allowed_domains", [])
        max_pages = config.get("max_pages", 500)
        product_url_pattern = config.get("product_url_pattern")

        all_urls: set[str] = set()
        for ep_url in entrypoints:
            if self._browser:
                try:
                    html = self._browser.fetch_page(ep_url)
                    links = self._extract_links(html, ep_url, allowed_domains)
                    all_urls.update(links)
                    logger.info(f"Crawled {len(links)} links from {ep_url}")
                except Exception as e:
                    logger.warning(f"Failed to crawl {ep_url}: {e}")
            else:
                logger.warning(f"No browser configured, skipping DOM crawl of {ep_url}")

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
