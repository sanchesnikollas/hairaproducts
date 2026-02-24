# src/extraction/deterministic.py
from __future__ import annotations

import json
import re
import logging

from src.core.models import ExtractionMethod
from src.extraction.evidence_tracker import create_evidence

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

def _get_soup(html: str):
    if BeautifulSoup is None:
        raise ImportError("beautifulsoup4 is required: pip install beautifulsoup4 lxml")
    return BeautifulSoup(html, "lxml")


def extract_jsonld(html: str) -> dict | None:
    soup = _get_soup(html)
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "Product":
                return data
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "Product":
                        return item
        except (json.JSONDecodeError, TypeError):
            continue
    return None


INCI_TAB_LABELS = [
    "composição", "composicao", "ingredientes", "ingredients",
    "inci", "composição do produto", "composição completa",
]

# UI text that leaks into INCI content from tab/filter buttons
TAB_NOISE_PREFIXES = [
    "todos", "all", "ver todos", "mostrar todos", "ver mais",
]


def _clean_tab_content(text: str) -> str:
    """Remove UI noise from tab content (filter buttons, etc.)."""
    for prefix in TAB_NOISE_PREFIXES:
        if text.lower().startswith(prefix):
            text = text[len(prefix):].lstrip()
    return text


def _extract_inci_by_tab_labels(soup) -> tuple[str | None, str | None]:
    """Find INCI content in collapsible tabs/accordions by label text."""
    # Strategy 1: Button/heading with label, content in next sibling
    for el in soup.find_all(["button", "h2", "h3", "h4", "a", "span", "div"]):
        text = el.get_text(strip=True).lower()
        if any(label == text or text.startswith(label) for label in INCI_TAB_LABELS):
            # Check next sibling
            sibling = el.find_next_sibling()
            if sibling:
                content = _clean_tab_content(sibling.get_text(strip=True))
                if content and len(content) > 30 and "," in content:
                    return content, f"tab-label:{text}"
            # Check parent's next sibling
            if el.parent:
                parent_sibling = el.parent.find_next_sibling()
                if parent_sibling:
                    content = _clean_tab_content(parent_sibling.get_text(strip=True))
                    if content and len(content) > 30 and "," in content:
                        return content, f"tab-label-parent:{text}"

    # Strategy 2: .collapse__content or .tab-content near composição text
    for cls in ["collapse__content", "tab-content", "tab-pane", "accordion-content"]:
        for el in soup.select(f".{cls}"):
            # Check if a previous sibling or parent has composição label
            prev = el.find_previous_sibling()
            if prev and any(label in prev.get_text().lower() for label in INCI_TAB_LABELS):
                content = _clean_tab_content(el.get_text(strip=True))
                if content and len(content) > 30 and "," in content:
                    return content, f".{cls}"

    return None, None


def extract_by_selectors(
    html: str,
    inci_selectors: list[str] | None = None,
    name_selectors: list[str] | None = None,
    image_selectors: list[str] | None = None,
) -> dict:
    soup = _get_soup(html)
    result: dict = {"name": None, "inci_raw": None, "image": None, "inci_selector": None, "name_selector": None}

    if name_selectors:
        for sel in name_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                result["name"] = el.get_text(strip=True)
                result["name_selector"] = sel
                break

    if inci_selectors:
        for sel in inci_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                result["inci_raw"] = el.get_text(strip=True)
                result["inci_selector"] = sel
                break

    # Fallback: tab-label heuristic for INCI
    if not result["inci_raw"]:
        inci_text, selector = _extract_inci_by_tab_labels(soup)
        if inci_text:
            result["inci_raw"] = inci_text
            result["inci_selector"] = selector

    if image_selectors:
        for sel in image_selectors:
            el = soup.select_one(sel)
            if el:
                src = el.get("src") or el.get("data-src")
                if src:
                    result["image"] = src
                    break

    return result


def extract_product_deterministic(
    html: str,
    url: str,
    inci_selectors: list[str] | None = None,
    name_selectors: list[str] | None = None,
) -> dict:
    evidence_list = []
    result = {
        "product_name": None,
        "image_url_main": None,
        "inci_raw": None,
        "description": None,
        "price": None,
        "currency": None,
        "evidence": evidence_list,
        "extraction_method": None,
    }

    # Try JSON-LD first
    jsonld = extract_jsonld(html)
    if jsonld:
        if jsonld.get("name"):
            result["product_name"] = jsonld["name"]
            evidence_list.append(create_evidence(
                "product_name", url, "json-ld @type=Product .name",
                jsonld["name"], ExtractionMethod.JSONLD,
            ))
        if jsonld.get("image"):
            img = jsonld["image"]
            if isinstance(img, list):
                img = img[0]
            result["image_url_main"] = img
            evidence_list.append(create_evidence(
                "image_url_main", url, "json-ld @type=Product .image",
                str(img), ExtractionMethod.JSONLD,
            ))
        if jsonld.get("description"):
            result["description"] = jsonld["description"]
        offers = jsonld.get("offers", {})
        if isinstance(offers, dict):
            if offers.get("price"):
                result["price"] = float(offers["price"])
                result["currency"] = offers.get("priceCurrency", "BRL")
        result["extraction_method"] = "jsonld"

    # Try CSS selectors to fill gaps
    default_name_selectors = name_selectors or ["h1.product-name", "h1", ".product-title"]
    default_inci_selectors = inci_selectors or [
        ".product-ingredients p", ".product-ingredients",
        "#composicao", "#ingredientes",
        "[data-tab='ingredientes']",
    ]

    sel_result = extract_by_selectors(
        html,
        inci_selectors=default_inci_selectors,
        name_selectors=default_name_selectors if not result["product_name"] else None,
        image_selectors=[".product-image", "img.product-img"] if not result["image_url_main"] else None,
    )

    if not result["product_name"] and sel_result["name"]:
        result["product_name"] = sel_result["name"]
        evidence_list.append(create_evidence(
            "product_name", url, sel_result["name_selector"] or "",
            sel_result["name"], ExtractionMethod.HTML_SELECTOR,
        ))

    if sel_result["inci_raw"]:
        result["inci_raw"] = sel_result["inci_raw"]
        evidence_list.append(create_evidence(
            "inci_ingredients", url, sel_result["inci_selector"] or "",
            sel_result["inci_raw"][:500], ExtractionMethod.HTML_SELECTOR,
        ))
        if not result["extraction_method"]:
            result["extraction_method"] = "html_selector"

    if not result["image_url_main"] and sel_result.get("image"):
        result["image_url_main"] = sel_result["image"]

    return result
