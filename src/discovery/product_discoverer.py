# src/discovery/product_discoverer.py
from __future__ import annotations

import logging

from src.core.models import DiscoveredURL
from src.discovery.blueprint_engine import load_blueprint, generate_blueprint
from src.discovery.platform_adapters.sitemap import SitemapAdapter
from src.discovery.platform_adapters.dom_crawler import DOMCrawlerAdapter

logger = logging.getLogger(__name__)


class ProductDiscoverer:
    def __init__(self, browser=None):
        self._browser = browser
        self._adapters = [
            SitemapAdapter(),
            DOMCrawlerAdapter(browser=browser),
        ]

    def discover(self, blueprint: dict) -> list[DiscoveredURL]:
        all_discovered: dict[str, DiscoveredURL] = {}

        discovery_config = blueprint.get("discovery", {})
        config = {
            "sitemap_urls": discovery_config.get("sitemap_urls", []),
            "entrypoints": blueprint.get("entrypoints", []),
            "allowed_domains": blueprint.get("allowed_domains", []),
            "max_pages": discovery_config.get("max_pages", 500),
            "product_url_pattern": discovery_config.get("product_url_pattern"),
        }

        for adapter in self._adapters:
            try:
                results = adapter.discover(config)
                for item in results:
                    if item.url not in all_discovered:
                        all_discovered[item.url] = item
                logger.info(f"Adapter {adapter.name}: found {len(results)} URLs")
            except Exception as e:
                logger.warning(f"Adapter {adapter.name} failed: {e}")

        discovered = list(all_discovered.values())
        logger.info(
            f"Total discovered: {len(discovered)} URLs "
            f"({sum(1 for d in discovered if d.hair_relevant)} hair-relevant, "
            f"{sum(1 for d in discovered if d.is_kit)} kits)"
        )
        return discovered

    def discover_for_brand(self, brand_slug: str, blueprints_dir: str | None = None) -> list[DiscoveredURL]:
        blueprint = load_blueprint(brand_slug, blueprints_dir)
        if not blueprint:
            logger.warning(f"No blueprint found for {brand_slug}")
            return []
        return self.discover(blueprint)
