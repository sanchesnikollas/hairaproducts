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
    "/busca/", "/search/", "/busca?",
]

PRODUCT_INDICATORS = [
    r"-\d+ml", r"-\d+g", r"/p$", r"/p/", r"/p\?",
    r"-shampoo-", r"-condicionador-", r"-mascara-",
]

# Pages that are never products
NON_PRODUCT_PATHS = [
    "about", "sobre", "contato", "contact", "fale-conosco",
    "blog", "politica", "privacy", "terms", "termos",
    "institucional", "quem-somos", "faq", "ajuda", "help",
    "trabalhe-conosco", "careers", "imprensa", "press",
    "loja-fisica", "stores", "store-locator",
]


def classify_url(url: str, product_url_pattern: str | None = None) -> URLType:
    lower = url.lower()
    path = lower.split("?")[0]
    query = lower.split("?")[1] if "?" in lower else ""

    # Check kit first
    for pattern in KIT_PATTERNS:
        if re.search(pattern, lower):
            return URLType.KIT

    # Check non-hair
    for kw in EXCLUDE_KEYWORDS:
        if f"/{kw}/" in lower or f"/{kw}" == path[-len(f"/{kw}"):]:
            return URLType.NON_HAIR

    # Check non-product info pages
    path_segments = [s for s in path.split("/") if s and "." not in s.split("/")[-1].split("?")[0] or s.endswith(".html")]
    # Strip domain
    if path.startswith("http"):
        path_segments = path.split("//", 1)[-1].split("/")[1:]
    for seg in path_segments:
        seg_clean = seg.replace(".html", "").split("?")[0]
        if seg_clean in NON_PRODUCT_PATHS:
            return URLType.OTHER

    # Check for search/category query patterns (e.g., busca/?cgid=...)
    if "cgid=" in query or "category=" in query:
        return URLType.CATEGORY

    # Check category
    for indicator in CATEGORY_INDICATORS:
        if indicator in lower and lower.rstrip("/").endswith(indicator.rstrip("/")):
            return URLType.CATEGORY
        if indicator in lower and lower.count("/") <= 4:
            indicator_clean = indicator.rstrip("/")
            segments = [s for s in path.split("/") if s]
            if len(segments) <= 4:
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
        segments = [s for s in path.split("/")[3:] if s]  # skip domain
        if len(segments) >= 2:
            return URLType.PRODUCT
        if segments and len(segments[0].split("-")) >= 3:
            return URLType.PRODUCT
        return URLType.CATEGORY

    return URLType.OTHER
