# src/discovery/url_classifier.py
from __future__ import annotations

import enum
import re

from src.core.taxonomy import HAIR_KEYWORDS, EXCLUDE_KEYWORDS, KIT_PATTERNS


class URLType(str, enum.Enum):
    PRODUCT = "product"
    CATEGORY = "category"
    KIT = "kit"
    NON_HAIR = "non_hair"
    OTHER = "other"


CATEGORY_INDICATORS = [
    "/cabelos/", "/cabelo/", "/hair/", "/produtos/", "/products/",
    "/collections/", "/categoria/", "/category/",
    "/shampoo/", "/condicionador/", "/tratamento/", "/finalizacao/",
    "/masculino/", "/men/",
]

PRODUCT_INDICATORS = [
    r"-\d+ml", r"-\d+g", r"/p$", r"/p/", r"\.html$",
    r"-shampoo-", r"-condicionador-", r"-mascara-",
]


def classify_url(url: str, product_url_pattern: str | None = None) -> URLType:
    lower = url.lower()

    # Check kit first
    for pattern in KIT_PATTERNS:
        if re.search(pattern, lower):
            return URLType.KIT

    # Check non-hair
    for kw in EXCLUDE_KEYWORDS:
        if f"/{kw}/" in lower or f"/{kw}" == lower.split("?")[0][-len(f"/{kw}"):]:
            return URLType.NON_HAIR

    # Check category
    for indicator in CATEGORY_INDICATORS:
        if indicator in lower and lower.rstrip("/").endswith(indicator.rstrip("/")):
            return URLType.CATEGORY
        if indicator in lower and lower.count("/") <= 4:
            # Likely a category if it's a short path with category indicator
            path = lower.split("?")[0]
            segments = [s for s in path.split("/") if s]
            if len(segments) <= 4:
                # Check if it looks like a product (has product-specific patterns)
                is_product = any(re.search(p, lower) for p in PRODUCT_INDICATORS)
                if not is_product:
                    return URLType.CATEGORY

    # Check product patterns
    if product_url_pattern:
        if re.search(product_url_pattern, lower):
            return URLType.PRODUCT

    for pattern in PRODUCT_INDICATORS:
        if re.search(pattern, lower):
            return URLType.PRODUCT

    # Check hair relevance by keywords in URL
    has_hair_keyword = any(kw.replace(" ", "-") in lower or kw.replace(" ", "") in lower for kw in HAIR_KEYWORDS[:20])
    if has_hair_keyword:
        path = lower.split("?")[0]
        segments = [s for s in path.split("/")[3:] if s]  # skip domain
        if len(segments) >= 2:
            return URLType.PRODUCT
        # Single segment: long hyphenated slug = product, short = category
        if segments and len(segments[0].split("-")) >= 3:
            return URLType.PRODUCT
        return URLType.CATEGORY

    return URLType.OTHER
