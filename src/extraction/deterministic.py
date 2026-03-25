# src/extraction/deterministic.py
from __future__ import annotations

import html as html_module
import json
import re
import logging

from src.core.models import ExtractionMethod
from src.extraction.evidence_tracker import create_evidence

logger = logging.getLogger(__name__)


def sanitize_text(text: str | None) -> str | None:
    """Clean text: decode HTML entities, strip tags, normalize whitespace."""
    if not text:
        return None
    # Decode HTML entities (&amp; &ccedil; &#233; etc.)
    cleaned = html_module.unescape(text)
    # Remove any residual HTML tags
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    # Normalize whitespace (collapse multiple spaces/newlines)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else None

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
    # Most specific labels first (longer matches take priority)
    "lista completa de ingredientes", "full ingredient list",
    "composição completa", "composição do produto",
    "composição", "composicao",
    "ingredientes", "ingredients", "inci",
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


def _looks_like_inci(text: str) -> bool:
    """Check if text looks like an INCI ingredient list (has separators and length)."""
    if not text or len(text) < 30:
        return False
    # Must contain ingredient-like separators
    return any(sep in text for sep in [",", ";", "●", "•", "·"])


def _label_priority(matched_label: str) -> int:
    """Lower number = higher priority. More specific labels get priority."""
    for i, label in enumerate(INCI_TAB_LABELS):
        if label == matched_label:
            return i
    return len(INCI_TAB_LABELS)


def _extract_inci_by_tab_labels(soup) -> tuple[str | None, str | None]:
    """Find INCI content in collapsible tabs/accordions by label text."""
    candidates: list[tuple[str, str, int]] = []  # (content, selector, priority)

    # Strategy 0: Accordion container pattern (e.g., O Boticário)
    # Heading inside a container div, content in a sibling/descendant region
    import re as _re
    for container in soup.find_all("div", class_=_re.compile(r"accordion.*padding|container.*padding")):
        heading = container.find(["h2", "h3", "h4"])
        if not heading:
            continue
        heading_text = heading.get_text(strip=True).lower()
        for label in INCI_TAB_LABELS:
            if label == heading_text or heading_text.startswith(label):
                priority = _label_priority(label)
                # Look for <p> or <li> content within the same container
                for p in container.find_all(["p", "li"]):
                    content = p.get_text(strip=True)
                    if _looks_like_inci(content):
                        candidates.append((content, f"accordion-container:{label}", priority))
                        break
                # Also check for region div (aria-controlled regions)
                region = container.find("div", id=_re.compile(r"region|content"))
                if region:
                    content = region.get_text(strip=True)
                    if _looks_like_inci(content):
                        candidates.append((content, f"accordion-region:{label}", priority))
                break

    # Strategy 1: Button/heading with label, content in nearby elements
    for el in soup.find_all(["button", "h2", "h3", "h4", "a", "span", "div", "strong", "p", "b"]):
        # Skip UI filter/topic elements (e.g., Shopify FAQ tab filters)
        el_classes = " ".join(el.get("class", []))
        if _re.search(r"filter[-_]?topic|faq[-_]?topic|tab[-_]?filter", el_classes):
            continue
        el_text_original = el.get_text(strip=True)
        el_text = el_text_original.lower()
        for label in INCI_TAB_LABELS:
            if label == el_text or el_text.startswith(label):
                priority = _label_priority(label)
                found = False

                # Check 1: Inline content — element text extends beyond label
                # (wrapper divs that contain both heading + INCI)
                if len(el_text) > len(label) + 30:
                    inline = _clean_tab_content(el_text_original[len(label):].strip())
                    if _looks_like_inci(inline):
                        # Prefer descendant <p> for cleaner extraction
                        for p in el.find_all("p"):
                            p_content = p.get_text(strip=True)
                            if _looks_like_inci(p_content):
                                candidates.append((p_content, f"tab-desc-p:{label}", priority))
                                found = True
                                break
                        if not found:
                            candidates.append((inline, f"tab-inline:{label}", priority))
                            found = True

                # Check 2: Next sibling element
                if not found:
                    sibling = el.find_next_sibling()
                    if sibling:
                        content = _clean_tab_content(sibling.get_text(strip=True))
                        if _looks_like_inci(content):
                            candidates.append((content, f"tab-label:{label}", priority))
                            found = True

                # Check 3: For headings/labels, find next <p> anywhere in DOM
                if not found and el.name in ("h2", "h3", "h4", "strong", "b"):
                    next_p = el.find_next("p")
                    if next_p:
                        content = next_p.get_text(strip=True)
                        if _looks_like_inci(content):
                            candidates.append((content, f"tab-heading-p:{label}", priority))
                            found = True

                # Check 4: Parent section — extract content after the LABEL (not el_text)
                if not found and el.parent:
                    parent_text = el.parent.get_text(strip=True)
                    idx = parent_text.lower().find(label)
                    if idx >= 0:
                        after = _clean_tab_content(parent_text[idx + len(label):].strip())
                        if _looks_like_inci(after):
                            candidates.append((after, f"tab-section:{label}", priority))
                            found = True

                    # Check 5: Parent's next sibling
                    if not found:
                        parent_sibling = el.parent.find_next_sibling()
                        if parent_sibling:
                            content = _clean_tab_content(parent_sibling.get_text(strip=True))
                            if _looks_like_inci(content):
                                candidates.append((content, f"tab-parent-sib:{label}", priority))

                break  # Only match the first (most specific) label

    # Strategy 2: .collapse__content or .tab-content near composição text
    for cls in ["collapse__content", "tab-content", "tab-pane", "accordion-content"]:
        for el in soup.select(f".{cls}"):
            prev = el.find_previous_sibling()
            if prev:
                prev_text = prev.get_text().lower()
                for label in INCI_TAB_LABELS:
                    # Use word boundary match to avoid false positives
                    # (e.g., "inci" matching inside "principais")
                    if _re.search(r"(?:^|\b)" + _re.escape(label) + r"(?:\b|$)", prev_text):
                        content = _clean_tab_content(el.get_text(strip=True))
                        if _looks_like_inci(content):
                            priority = _label_priority(label)
                            candidates.append((content, f".{cls}", priority))
                        break

    if not candidates:
        return None, None

    # Return the candidate with the highest priority (lowest number)
    candidates.sort(key=lambda x: x[2])
    return candidates[0][0], candidates[0][1]


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
                src = el.get("data-src") or el.get("src")
                # Skip data URIs (lazy-loading placeholders)
                if src and src.startswith("data:"):
                    src = el.get("data-src")
                if src:
                    result["image"] = src
                    break

    # Fallback: extract image from Vue media-gallery :variants JSON
    if not result["image"]:
        gallery = soup.select_one("media-gallery[\\:variants]")
        if gallery:
            import json as _json
            try:
                variants_json = gallery.get(":variants", "")
                variants = _json.loads(variants_json)
                if variants and isinstance(variants, list):
                    first = variants[0]
                    images = first.get("images", [])
                    if images and isinstance(images, list):
                        first_img_set = images[0]
                        if isinstance(first_img_set, list):
                            for img_entry in first_img_set:
                                if isinstance(img_entry, dict) and img_entry.get("src"):
                                    result["image"] = img_entry["src"]
                                    break
            except (_json.JSONDecodeError, KeyError, IndexError, TypeError):
                pass

    return result


def _is_waf_challenge_page(html: str) -> bool:
    """Detect Cloudflare/WAF challenge pages that don't contain real product content."""
    lower = html[:5000].lower()
    challenge_markers = [
        "just a moment",
        "um momento",
        "cf-challenge",
        "cf-turnstile",
        "challenges.cloudflare.com",
        "_cf_chl_opt",
    ]
    return any(marker in lower for marker in challenge_markers)


def _is_domain_name(text: str) -> bool:
    """Check if text looks like a domain name rather than a product name."""
    if not text:
        return False
    text = text.strip().lower()
    # Matches patterns like "www.example.com" or "example.com.br"
    return bool(re.match(r'^(www\.)?[a-z0-9-]+\.[a-z]{2,}(\.[a-z]{2,})?$', text))


def extract_product_deterministic(
    html: str,
    url: str,
    inci_selectors: list[str] | None = None,
    name_selectors: list[str] | None = None,
    image_selectors: list[str] | None = None,
    section_label_map: dict | None = None,
) -> dict:
    evidence_list = []
    result = {
        "product_name": None,
        "image_url_main": None,
        "inci_raw": None,
        "inci_source": None,
        "description": None,
        "care_usage": None,
        "composition": None,
        "price": None,
        "currency": None,
        "evidence": evidence_list,
        "extraction_method": None,
    }

    # Detect WAF/Cloudflare challenge pages early
    if _is_waf_challenge_page(html):
        logger.warning(f"WAF challenge page detected for {url}, skipping extraction")
        return result

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
            if isinstance(img, dict):
                img = img.get("url") or img.get("contentUrl") or img.get("src")
            if isinstance(img, str):
                result["image_url_main"] = img
            evidence_list.append(create_evidence(
                "image_url_main", url, "json-ld @type=Product .image",
                str(img), ExtractionMethod.JSONLD,
            ))
        if jsonld.get("description"):
            result["description"] = sanitize_text(jsonld["description"])
        offers = jsonld.get("offers", {})
        if isinstance(offers, dict):
            price = offers.get("price") or offers.get("lowPrice")
            # Check nested offers array (AggregateOffer pattern)
            if not price and isinstance(offers.get("offers"), list) and offers["offers"]:
                price = offers["offers"][0].get("price")
            if price:
                result["price"] = float(price)
                result["currency"] = offers.get("priceCurrency", "BRL")
        result["extraction_method"] = "jsonld"

    # Section classifier: extract taxonomy fields from headings
    if section_label_map:
        from src.extraction.section_classifier import extract_sections_from_html
        section_result = extract_sections_from_html(html, section_label_map)
        if section_result.care_usage and not result["care_usage"]:
            result["care_usage"] = section_result.care_usage
        if section_result.composition and not result["composition"]:
            result["composition"] = section_result.composition
        if section_result.ingredients_inci_raw and not result["inci_raw"]:
            result["inci_raw"] = section_result.ingredients_inci_raw
            result["inci_source"] = "section_classifier"
        if section_result.description and not result["description"]:
            result["description"] = section_result.description
        # Create evidence entries for section-extracted fields
        for section in section_result.sections:
            evidence_list.append(create_evidence(
                section.taxonomy_field, url, section.selector,
                section.content[:500], ExtractionMethod.HTML_SELECTOR,
                source_section_label=section.source_section_label,
            ))

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
        image_selectors=(image_selectors or [".product-image", "img.product-img"]) if not result["image_url_main"] else None,
    )

    if not result["product_name"] and sel_result["name"]:
        result["product_name"] = sanitize_text(sel_result["name"])
        evidence_list.append(create_evidence(
            "product_name", url, sel_result["name_selector"] or "",
            sel_result["name"], ExtractionMethod.HTML_SELECTOR,
        ))

    if sel_result["inci_raw"] and not result["inci_raw"]:
        result["inci_raw"] = sel_result["inci_raw"]
        evidence_list.append(create_evidence(
            "inci_ingredients", url, sel_result["inci_selector"] or "",
            sel_result["inci_raw"][:500], ExtractionMethod.HTML_SELECTOR,
        ))
        if not result["extraction_method"]:
            result["extraction_method"] = "html_selector"
        # Determine inci_source: tab label heuristic selectors start with "tab-" or "accordion-"
        _inci_sel = sel_result.get("inci_selector") or ""
        if _inci_sel.startswith(("tab-", "accordion-")) or _inci_sel.startswith(".") and any(
            cls in _inci_sel for cls in ["collapse__content", "tab-content", "tab-pane", "accordion-content"]
        ):
            result["inci_source"] = "tab_label_heuristic"
        else:
            result["inci_source"] = "css_selector"

    if not result["image_url_main"] and sel_result.get("image"):
        result["image_url_main"] = sel_result["image"]

    # Image fallback: og:image meta tag
    if not result["image_url_main"]:
        soup = _get_soup(html)
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            result["image_url_main"] = og_img["content"]

    # Guard: reject product names that are actually domain names (WAF artifact)
    if result["product_name"] and _is_domain_name(result["product_name"]):
        logger.warning(
            f"Product name looks like a domain name: '{result['product_name']}' "
            f"for {url} — likely a WAF challenge page, clearing extraction"
        )
        result["product_name"] = None

    return result
