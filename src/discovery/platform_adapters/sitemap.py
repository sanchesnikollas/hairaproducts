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

# Default headers — alguns WAFs (Akamai, Cloudflare) bloqueiam o UA
# padrão `python-httpx/X.X.X`. Safari macOS funciona em 95% dos sites
# brasileiros (Chrome às vezes é bloqueado, Bot-detection nos sitemaps).
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "application/xml,text/xml,*/*;q=0.9",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


class SitemapAdapter(BaseAdapter):
    name = "sitemap"

    def __init__(self, timeout: float = 15.0, ssl_verify: bool = True, use_curl_cffi: bool = False):
        self._timeout = timeout
        self._ssl_verify = ssl_verify
        self._use_curl_cffi = use_curl_cffi
        self._curl_session = None

    def _fetch_via_curl_cffi(self, url: str) -> str | None:
        """Fallback escudado por WAFs (Akamai, Cloudflare) que fazem TLS
        fingerprinting (JA3). curl_cffi com `impersonate='chrome'` emula
        o handshake real do Chrome — passa onde httpx falha."""
        try:
            if self._curl_session is None:
                from curl_cffi.requests import Session
                self._curl_session = Session(impersonate="chrome", verify=self._ssl_verify)
            resp = self._curl_session.get(url, timeout=self._timeout)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text
            logger.debug(f"curl_cffi {resp.status_code} for {url}")
        except Exception as e:
            logger.debug(f"curl_cffi failed for {url}: {e}")
        return None

    def _fetch_sitemap(self, url: str) -> str | None:
        """Tenta httpx com UA Safari primeiro (rápido, dep leve). Se WAF
        bloquear (403/405/429), automaticamente cai pra curl_cffi com
        Chrome impersonation (passa Akamai/Cloudflare na maioria das vezes).

        `use_curl_cffi=True` força o fallback direto (skip httpx).
        """
        if self._use_curl_cffi:
            return self._fetch_via_curl_cffi(url)

        try:
            resp = httpx.get(
                url,
                timeout=self._timeout,
                follow_redirects=True,
                verify=self._ssl_verify,
                headers=_DEFAULT_HEADERS,
            )
            if resp.status_code == 200 and resp.text.strip():
                return resp.text
            # WAF típico: 403 (bot detected), 405 (method blocked), 429 (rate)
            # → tenta curl_cffi como fallback antes de desistir
            if resp.status_code in (403, 405, 429):
                logger.debug(
                    f"httpx got {resp.status_code} for {url}, falling back to curl_cffi"
                )
                return self._fetch_via_curl_cffi(url)
        except Exception as e:
            logger.debug(f"httpx failed for {url}: {e}, trying curl_cffi")
            return self._fetch_via_curl_cffi(url)
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
