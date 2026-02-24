# src/discovery/blueprint_engine.py
from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

from src.core.models import Brand

logger = logging.getLogger(__name__)

BLUEPRINTS_DIR = Path("config/blueprints")

# Known platform patterns
VTEX_PATTERNS = [
    r"\.vtexcommercestable\.com", r"\.vteximg\.com",
    r"/api/catalog_system/", r"vtex",
]
SHOPIFY_PATTERNS = [
    r"\.myshopify\.com", r"/collections/", r"cdn\.shopify\.com",
]
WOOCOMMERCE_PATTERNS = [
    r"/wp-content/", r"/wp-json/wc/", r"woocommerce",
]

# Default INCI CSS selectors to try per platform
DEFAULT_INCI_SELECTORS = {
    "vtex": [
        ".vtex-store-components-3-x-productDescriptionText p",
        ".vtex-tab-layout-0-x-contentContainer p",
        "#tab-ingredientes p", "#tab-composicao p",
    ],
    "shopify": [
        ".product__description p", ".product-single__description p",
        ".product-description p",
    ],
    "custom": [
        ".product-ingredients p", ".product-ingredients",
        "#ingredientes p", "#composicao p",
        "[data-tab='ingredientes'] p",
        ".product-description p",
    ],
}


def detect_platform(url: str) -> str:
    lower = url.lower()
    for pattern in VTEX_PATTERNS:
        if re.search(pattern, lower):
            return "vtex"
    for pattern in SHOPIFY_PATTERNS:
        if re.search(pattern, lower):
            return "shopify"
    for pattern in WOOCOMMERCE_PATTERNS:
        if re.search(pattern, lower):
            return "woocommerce"
    return "custom"


def generate_blueprint(brand: Brand, platform: str | None = None) -> dict:
    if platform is None:
        platform = detect_platform(brand.official_url_root)

    parsed = urlparse(brand.official_url_root)
    domain = parsed.hostname or ""

    entrypoints = list(brand.catalog_entrypoints)
    if not entrypoints and brand.official_url_root:
        entrypoints = [brand.official_url_root]

    blueprint = {
        "brand_slug": brand.brand_slug,
        "brand_name": brand.brand_name,
        "platform": platform,
        "domain": domain,
        "allowed_domains": [domain] if domain else [],
        "entrypoints": entrypoints,
        "discovery": {
            "strategy": "sitemap_first",
            "sitemap_urls": [
                f"{brand.official_url_root.rstrip('/')}/sitemap.xml",
            ],
            "product_url_pattern": None,
            "max_pages": 500,
            "pagination": {
                "type": "scroll",
                "max_pages": 10,
            },
        },
        "extraction": {
            "inci_selectors": DEFAULT_INCI_SELECTORS.get(platform, DEFAULT_INCI_SELECTORS["custom"]),
            "name_selectors": ["h1.product-name", "h1", ".product-title", ".product-name"],
            "image_selectors": [".product-image img", "img.product-img", ".gallery img"],
            "wait_for_selector": None,
            "use_llm_fallback": True,
        },
        "version": 1,
    }

    return blueprint


def save_blueprint(blueprint: dict, output_dir: str | None = None) -> Path:
    base_dir = Path(output_dir) if output_dir else BLUEPRINTS_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    filepath = base_dir / f"{blueprint['brand_slug']}.yaml"
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(blueprint, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    logger.info(f"Saved blueprint to {filepath}")
    return filepath


def load_blueprint(brand_slug: str, blueprints_dir: str | None = None) -> dict | None:
    base_dir = Path(blueprints_dir) if blueprints_dir else BLUEPRINTS_DIR
    filepath = base_dir / f"{brand_slug}.yaml"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
