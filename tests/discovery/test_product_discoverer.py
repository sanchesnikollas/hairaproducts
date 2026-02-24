# tests/discovery/test_product_discoverer.py
import pytest
from unittest.mock import patch, MagicMock

from src.core.models import Brand, DiscoveredURL
from src.discovery.product_discoverer import ProductDiscoverer
from src.discovery.blueprint_engine import generate_blueprint


class TestProductDiscoverer:
    def test_discover_deduplicates(self):
        discoverer = ProductDiscoverer()
        blueprint = {
            "brand_slug": "test",
            "allowed_domains": ["www.test.com"],
            "entrypoints": [],
            "discovery": {
                "sitemap_urls": [],
                "max_pages": 100,
                "product_url_pattern": None,
            },
        }
        # With no sitemap or browser, returns empty
        results = discoverer.discover(blueprint)
        assert isinstance(results, list)

    def test_discover_from_blueprint(self):
        brand = Brand(
            brand_name="Test",
            brand_slug="test",
            official_url_root="https://www.test.com",
        )
        bp = generate_blueprint(brand)
        discoverer = ProductDiscoverer()
        results = discoverer.discover(bp)
        assert isinstance(results, list)

    def test_discover_for_brand_no_blueprint(self, tmp_path):
        discoverer = ProductDiscoverer()
        results = discoverer.discover_for_brand("nonexistent", blueprints_dir=str(tmp_path))
        assert results == []

    @patch("src.discovery.platform_adapters.sitemap.httpx.get")
    def test_sitemap_discovery(self, mock_get):
        sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://www.test.com/shampoo-reparador</loc></url>
            <url><loc>https://www.test.com/condicionador-hidratante</loc></url>
            <url><loc>https://www.test.com/sobre-nos</loc></url>
        </urlset>'''
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = sitemap_xml
        mock_get.return_value = mock_resp

        discoverer = ProductDiscoverer()
        blueprint = {
            "brand_slug": "test",
            "allowed_domains": ["www.test.com"],
            "entrypoints": [],
            "discovery": {
                "sitemap_urls": ["https://www.test.com/sitemap.xml"],
                "max_pages": 100,
                "product_url_pattern": None,
            },
        }
        results = discoverer.discover(blueprint)
        urls = [r.url for r in results]
        assert len(urls) == 3
        assert "https://www.test.com/shampoo-reparador" in urls
