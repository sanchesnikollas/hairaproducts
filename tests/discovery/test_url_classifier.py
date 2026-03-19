# tests/discovery/test_url_classifier.py
import pytest
from src.discovery.url_classifier import classify_url, URLType


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
