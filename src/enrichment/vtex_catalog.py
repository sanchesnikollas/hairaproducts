from __future__ import annotations

import json
import logging
import re
from typing import Iterable
from urllib.parse import urlparse

logger = logging.getLogger("haira.enrichment.vtex_catalog")

# Spec keys (case-insensitive) considered to carry the INCI list / composição
INCI_SPEC_KEYS = (
    "composição",
    "composicao",
    "ingredientes",
    "ingredients",
    "inci",
    "composição (inci)",
    "lista de ingredientes",
    "composição do produto",
)

# Spec keys whose values we want to expose for description fallback
DESC_SPEC_KEYS = (
    "descrição",
    "descricao",
    "description",
    "sobre o produto",
    "informações do produto",
    "informacoes do produto",
)


def _extract_product_id(html: str) -> str | None:
    """Find a VTEX productId in the SSR HTML. VTEX consistently embeds it as JSON."""
    for pattern in (
        r'"productId"\s*:\s*"?(\d+)"?',
        r'"product_id"\s*:\s*"?(\d+)"?',
        r"productId\s*=\s*['\"]?(\d+)['\"]?",
        r'data-product-id\s*=\s*"(\d+)"',
    ):
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    return None


def _origin_from_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _normalize_key(key: str) -> str:
    return key.strip().lower()


def _find_spec_value(product: dict, keys: Iterable[str]) -> tuple[str | None, str | None]:
    """Look through product specs for any key in `keys` (case-insensitive).

    Returns (matched_key, joined_value) or (None, None).
    """
    if not isinstance(product, dict):
        return None, None
    norm_keys = {_normalize_key(k) for k in keys}

    # Strategy 1: allSpecifications + flat keys
    for spec_name in product.get("allSpecifications", []) or []:
        if _normalize_key(spec_name) in norm_keys:
            val = product.get(spec_name)
            if isinstance(val, list) and val:
                return spec_name, " | ".join(str(v) for v in val if v)
            if isinstance(val, str) and val:
                return spec_name, val

    # Strategy 2: properties array (some VTEX shapes use this)
    for prop in product.get("properties", []) or []:
        if isinstance(prop, dict):
            name = prop.get("name") or ""
            if _normalize_key(name) in norm_keys:
                values = prop.get("values") or []
                if isinstance(values, list) and values:
                    return name, " | ".join(str(v) for v in values if v)

    # Strategy 3: SKU-level specifications (items[0].productSpecifications, items[0].variations)
    items = product.get("items") or []
    if isinstance(items, list) and items:
        first = items[0] if isinstance(items[0], dict) else {}
        for prop in first.get("variations", []) or []:
            if isinstance(prop, dict):
                name = prop.get("name") or ""
                if _normalize_key(name) in norm_keys:
                    values = prop.get("values") or []
                    if isinstance(values, list) and values:
                        return name, " | ".join(str(v) for v in values if v)

    return None, None


def fetch_vtex_specs(curl_session, product_url: str, ssr_html: str | None = None) -> dict | None:
    """Resolve product specs via VTEX public catalog API.

    Returns a dict with keys: product_name, inci_raw, description, image, all_specs, used_api.
    Returns None if no productId was found in the SSR HTML or the API was unreachable.
    """
    # Get HTML if not provided (caller will usually pass it)
    if ssr_html is None:
        try:
            resp = curl_session.get(product_url, timeout=30)
            if resp.status_code != 200:
                return None
            ssr_html = resp.text
        except Exception as e:
            logger.debug("vtex_catalog: HTML fetch failed for %s: %s", product_url, e)
            return None

    pid = _extract_product_id(ssr_html or "")
    if not pid:
        return None

    origin = _origin_from_url(product_url)
    api_url = f"{origin}/api/catalog_system/pub/products/search?fq=productId:{pid}"
    try:
        resp = curl_session.get(api_url, timeout=30)
    except Exception as e:
        logger.debug("vtex_catalog: API request failed for %s: %s", api_url, e)
        return None

    if resp.status_code not in (200, 206):
        logger.debug("vtex_catalog: API status=%s for %s", resp.status_code, api_url)
        return None

    try:
        data = resp.json()
    except Exception:
        return None

    if not data or not isinstance(data, list):
        return None
    product = data[0]
    if not isinstance(product, dict):
        return None

    spec_key, inci_value = _find_spec_value(product, INCI_SPEC_KEYS)

    # Description: combine official description with composição-related spec hints
    description = product.get("description") or ""

    # Sometimes INCI is embedded inside the description body
    inci_from_desc = None
    if not inci_value and description:
        inci_from_desc = _extract_inci_from_description(description)

    name = product.get("productName") or product.get("productTitle") or None
    image = None
    items = product.get("items") or []
    if items and isinstance(items[0], dict):
        for img in items[0].get("images", []) or []:
            if isinstance(img, dict) and img.get("imageUrl"):
                image = img["imageUrl"]
                break

    return {
        "product_id": pid,
        "product_name": name,
        "inci_raw": inci_value or inci_from_desc,
        "inci_source_key": spec_key or ("description_body" if inci_from_desc else None),
        "description": description,
        "image_url_main": image,
        "all_specs": product.get("allSpecifications") or [],
        "used_api": True,
    }


# Patterns that mark the start of an inline INCI block in a description body.
# We accept any non-letter boundary before the keyword so we cover
# "\xa0\nCOMPOSIÇÃO:" and "</p><p>Composição:" style content. The pattern is
# anchored on the keyword followed by a colon/dash so it does not match the
# word "composição" used inline in marketing copy.
_INCI_HEADER = re.compile(
    r"(?:^|[^a-zA-ZÀ-ÿ])(composi[cç][aã]o(?:\s*\(inci\))?|ingredientes|ingredients|inci)\s*[:\-]\s*",
    re.IGNORECASE,
)
# Stop the INCI block at the next sentence/heading/HTML tag we recognize
_INCI_FOOTER = re.compile(
    r"<(?:p|h[1-6]|br|/p|/h[1-6]|div)\b|"
    r"\b(?:modo\s+de\s+uso|como\s+usar|how\s+to\s+use|directions|"
    r"benef[ií]cios|benefits|advert[eê]ncia|warnings|"
    r"validade|reg\.\s*ms|sac|cnpj|fabricante)\b",
    re.IGNORECASE,
)


def _extract_inci_from_description(description: str) -> str | None:
    """Extract an INCI block from a product description body (HTML or plain).

    Looks for "Composição: ...", "INCI: ...", "Ingredientes: ..." followed by a list
    of ingredients separated by commas / semicolons / bullets. Returns None if no
    plausible ingredient block is found.
    """
    if not description or len(description) < 30:
        return None

    # Strip simple HTML tags (we keep punctuation that delimits ingredient lists)
    # but use the raw text to detect the header
    header_match = _INCI_HEADER.search(description)
    if not header_match:
        return None

    start = header_match.end()
    tail = description[start:]
    footer_match = _INCI_FOOTER.search(tail)
    end = footer_match.start() if footer_match else min(len(tail), 4000)
    candidate = tail[:end]

    # Strip any HTML
    candidate = re.sub(r"<[^>]+>", " ", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" .;,")

    if len(candidate) < 30:
        return None
    # Require ingredient-list-like separators
    if not any(sep in candidate for sep in [",", ";", "|", "·", "•"]):
        return None
    return candidate
