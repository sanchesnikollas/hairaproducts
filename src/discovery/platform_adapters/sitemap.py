# src/discovery/platform_adapters/sitemap.py
from __future__ import annotations

import logging
import re
from xml.etree import ElementTree

import httpx

from src.core.models import DiscoveredURL
from src.discovery.platform_adapters.base import BaseAdapter
from src.discovery.url_classifier import classify_url, URLType

logger = logging.getLogger(__name__)

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class SitemapAdapter(BaseAdapter):
    name = "sitemap"

    def __init__(self, timeout: float = 15.0):
        self._timeout = timeout

    def _fetch_sitemap(self, url: str) -> str | None:
        try:
            resp = httpx.get(url, timeout=self._timeout, follow_redirects=True)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text
        except Exception as e:
            logger.debug(f"Failed to fetch sitemap {url}: {e}")
        return None

    def _parse_urls(self, xml_text: str) -> list[str]:
        urls = []
        try:
            root = ElementTree.fromstring(xml_text)
            # Check if it's a sitemap index
            for sitemap in root.findall("sm:sitemap", SITEMAP_NS):
                loc = sitemap.find("sm:loc", SITEMAP_NS)
                if loc is not None and loc.text:
                    child_xml = self._fetch_sitemap(loc.text.strip())
                    if child_xml:
                        urls.extend(self._parse_urls(child_xml))
            # Parse URL entries
            for url_elem in root.findall("sm:url", SITEMAP_NS):
                loc = url_elem.find("sm:loc", SITEMAP_NS)
                if loc is not None and loc.text:
                    urls.append(loc.text.strip())
        except ElementTree.ParseError as e:
            logger.warning(f"Failed to parse sitemap XML: {e}")
        return urls

    def discover(self, config: dict) -> list[DiscoveredURL]:
        sitemap_urls = config.get("sitemap_urls", [])
        max_pages = config.get("max_pages", 500)
        product_url_pattern = config.get("product_url_pattern")

        all_urls: set[str] = set()
        for sitemap_url in sitemap_urls:
            xml_text = self._fetch_sitemap(sitemap_url)
            if xml_text:
                parsed = self._parse_urls(xml_text)
                all_urls.update(parsed)
                logger.info(f"Found {len(parsed)} URLs in {sitemap_url}")

        discovered: list[DiscoveredURL] = []
        for url in list(all_urls)[:max_pages]:
            url_type = classify_url(url, product_url_pattern)
            discovered.append(DiscoveredURL(
                url=url,
                source_type="sitemap",
                hair_relevant=url_type in (URLType.PRODUCT, URLType.CATEGORY),
                hair_relevance_reason=f"url_type={url_type.value}",
                is_kit=url_type == URLType.KIT,
            ))

        return discovered
