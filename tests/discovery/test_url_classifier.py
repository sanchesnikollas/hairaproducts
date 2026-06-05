# tests/discovery/test_url_classifier.py
import pytest
from src.discovery.url_classifier import (
    URLType,
    classify_url,
    normalize_discovery_url,
)


class TestClassifyUrl:
    def test_product_url(self):
        assert classify_url("https://www.amend.com.br/shampoo-gold-black-reparador") == URLType.PRODUCT

    def test_category_url(self):
        assert classify_url("https://www.amend.com.br/cabelos/shampoo") == URLType.CATEGORY

    def test_kit_url(self):
        assert classify_url("https://www.amend.com.br/kit-shampoo-condicionador") == URLType.KIT

    def test_non_hair_url(self):
        assert classify_url("https://www.amend.com.br/corpo/hidratante-corporal") == URLType.NON_HAIR

    def test_unknown_url(self):
        assert classify_url("https://www.amend.com.br/sobre-nos") == URLType.OTHER


class TestNormalizeDiscoveryUrl:
    def test_strips_fragment(self):
        assert normalize_discovery_url("https://x.com/p/foo.html#site-content") == "https://x.com/p/foo.html"

    def test_strips_tracking_params(self):
        url = "https://x.com/p/foo.html?gclid=abc&utm_source=email&fbclid=xyz"
        assert normalize_discovery_url(url) == "https://x.com/p/foo.html"

    def test_strips_listing_params(self):
        url = "https://x.com/shampoos/?prefn1=hairType&prefv1=Oleoso&start=0&sz=24"
        assert normalize_discovery_url(url) == "https://x.com/shampoos/"

    def test_preserves_dwvar_size_variant(self):
        # Demandware size variants identify distinct SKUs — keep them
        url = "https://x.com/p/foo.html?dwvar_FOO_size=200ML"
        assert normalize_discovery_url(url) == "https://x.com/p/foo.html?dwvar_FOO_size=200ML"

    def test_mixed_params_keeps_only_real(self):
        url = "https://x.com/p/foo.html?dwvar_X_size=200&utm_source=fb&gclid=z"
        assert normalize_discovery_url(url) == "https://x.com/p/foo.html?dwvar_X_size=200"

    def test_preserves_cgid_category(self):
        url = "https://x.com/busca?cgid=hair-care"
        assert normalize_discovery_url(url) == "https://x.com/busca?cgid=hair-care"

    def test_pure_listing_collapses_to_path(self):
        url = "https://x.com/shampoos/?prefn1=type#footer-nav"
        assert normalize_discovery_url(url) == "https://x.com/shampoos/"

    def test_invalid_url_returns_none(self):
        assert normalize_discovery_url("") is None
        assert normalize_discovery_url("not-a-url") is None
        assert normalize_discovery_url("/relative/path") is None

    def test_clean_url_unchanged(self):
        url = "https://x.com/p/foo.html"
        assert normalize_discovery_url(url) == url

    def test_idempotent(self):
        url = "https://x.com/p/foo.html?prefn1=x#frag"
        once = normalize_discovery_url(url)
        twice = normalize_discovery_url(once)
        assert once == twice
