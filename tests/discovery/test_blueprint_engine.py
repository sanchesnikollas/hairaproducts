# tests/discovery/test_blueprint_engine.py
import pytest
from pathlib import Path

from src.core.models import Brand
from src.discovery.blueprint_engine import (
    detect_platform,
    generate_blueprint,
    save_blueprint,
    load_blueprint,
)


class TestDetectPlatform:
    def test_vtex(self):
        assert detect_platform("https://loja.amend.com.br.vtexcommercestable.com") == "vtex"

    def test_shopify(self):
        assert detect_platform("https://store.myshopify.com/collections/hair") == "shopify"

    def test_custom(self):
        assert detect_platform("https://www.amend.com.br") == "custom"

    def test_woocommerce(self):
        assert detect_platform("https://example.com/wp-content/themes/shop") == "woocommerce"


class TestGenerateBlueprint:
    def test_generates_valid_blueprint(self):
        brand = Brand(
            brand_name="Amend",
            brand_slug="amend",
            official_url_root="https://www.amend.com.br",
        )
        bp = generate_blueprint(brand)
        assert bp["brand_slug"] == "amend"
        assert bp["platform"] == "custom"
        assert bp["domain"] == "www.amend.com.br"
        assert "www.amend.com.br" in bp["allowed_domains"]
        assert len(bp["extraction"]["inci_selectors"]) > 0
        assert bp["version"] == 1

    def test_uses_catalog_entrypoints(self):
        brand = Brand(
            brand_name="Truss",
            brand_slug="truss",
            official_url_root="https://www.truss.com.br",
            catalog_entrypoints=["https://www.truss.com.br/produtos"],
        )
        bp = generate_blueprint(brand)
        assert "https://www.truss.com.br/produtos" in bp["entrypoints"]

    def test_vtex_selectors(self):
        brand = Brand(
            brand_name="Test",
            brand_slug="test",
            official_url_root="https://www.test.com.br",
        )
        bp = generate_blueprint(brand, platform="vtex")
        assert bp["platform"] == "vtex"
        assert any("vtex" in s for s in bp["extraction"]["inci_selectors"])


class TestSaveAndLoadBlueprint:
    def test_save_and_load(self, tmp_path):
        brand = Brand(
            brand_name="Amend",
            brand_slug="amend",
            official_url_root="https://www.amend.com.br",
        )
        bp = generate_blueprint(brand)
        filepath = save_blueprint(bp, output_dir=str(tmp_path))
        assert filepath.exists()

        loaded = load_blueprint("amend", blueprints_dir=str(tmp_path))
        assert loaded is not None
        assert loaded["brand_slug"] == "amend"
        assert loaded["domain"] == "www.amend.com.br"

    def test_load_nonexistent(self, tmp_path):
        loaded = load_blueprint("nonexistent", blueprints_dir=str(tmp_path))
        assert loaded is None
