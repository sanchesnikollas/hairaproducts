# src/extraction/section_classifier.py
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


@dataclass
class PageSection:
    label: str
    content: str
    selector: str
    element_tag: str
    taxonomy_field: str
    source_section_label: str


@dataclass
class SectionExtractionResult:
    description: str | None = None
    care_usage: str | None = None
    composition: str | None = None
    ingredients_inci_raw: str | None = None
    sections: list[PageSection] = field(default_factory=list)


# Marketing verbs that indicate promotional text, not INCI
MARKETING_VERBS_PT = [
    "descubra", "transforme", "desenvolvid", "proporciona", "garante",
    "promove", "combate", "nutre", "hidrata", "fortalece", "repara",
    "protege", "revitaliza", "restaura", "rejuvenesce",
]

# Usage verbs that indicate application instructions, not INCI
USAGE_VERBS_PT = [
    "aplique", "massageie", "enxague", "enxágue", "deixe agir", "espalhe",
    "penteie", "seque", "lave", "misture", "utilize",
]

MARKETING_VERBS_EN = [
    "discover", "transform", "developed", "provides", "ensures",
    "promotes", "fights", "nourishes", "moisturizes", "strengthens",
]

USAGE_VERBS_EN = [
    "apply", "massage", "rinse", "leave on", "spread", "comb",
    "dry", "wash", "mix", "use on",
]

ALL_REJECTION_VERBS = MARKETING_VERBS_PT + USAGE_VERBS_PT + MARKETING_VERBS_EN + USAGE_VERBS_EN

# Heading-like elements to search for section labels
HEADING_TAGS = ["h2", "h3", "h4", "button", "strong", "b", "span"]


def _normalize_label(text: str) -> str:
    """Lowercase, strip accents, strip emojis/symbols, normalize whitespace."""
    # NFD decomposition then strip combining marks
    nfkd = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    result = re.sub(r"\s+", " ", stripped).strip().lower()
    # Strip leading emojis, symbols, and other non-alphanumeric characters
    # (e.g., "🧴 composição:" -> "composicao:")
    result = re.sub(r"^[^\w]+", "", result)
    return result


def validate_inci_content(text: str | None) -> bool:
    """Check if text is a valid INCI ingredient list.

    Anti-error checks:
    - Must have ingredient-like separators (, or ● or • or ·)
    - Must be at least 30 chars long
    - Must not contain marketing or usage verbs
    """
    if not text or len(text) < 30:
        return False
    # Must contain ingredient-like separators
    if not any(sep in text for sep in [",", ";", "●", "•", "·"]):
        return False
    # Reject if contains marketing or usage verbs
    text_lower = text.lower()
    for verb in ALL_REJECTION_VERBS:
        if verb in text_lower:
            return False
    return True


def _get_soup(html: str):
    if BeautifulSoup is None:
        raise ImportError("beautifulsoup4 is required: pip install beautifulsoup4 lxml")
    return BeautifulSoup(html, "lxml")


def _extract_content_after_heading(el) -> str | None:
    """Extract text content following a heading element."""
    # Strategy 0: <details>/<summary> accordion pattern
    # Structure: <details><summary>...<span>Label</span>...</summary><div class="accordion__content">...</div></details>
    # Walk up to find <summary> ancestor (may be nested inside toggle divs)
    ancestor = el.parent
    for _ in range(4):
        if ancestor is None:
            break
        if ancestor.name == "summary":
            details = ancestor.parent
            if details and details.name == "details":
                content_div = details.find("div", class_=re.compile(r"accordion.*(content|body|panel)"))
                if content_div:
                    content = content_div.get_text(strip=True)
                    if content:
                        return content
            break
        ancestor = ancestor.parent

    # Strategy 1: For inline labels (strong/b), prefer parent's text after the label
    # This handles <p><strong>Ingredientes:</strong> Aqua, Cetearyl Alcohol, ...</p>
    if el.name in ("strong", "b") and el.parent:
        parent_text = el.parent.get_text(strip=True)
        el_text = el.get_text(strip=True)
        idx = parent_text.find(el_text)
        if idx >= 0:
            after = parent_text[idx + len(el_text):].strip()
            if after:
                return after

    # Strategy 2: Next sibling element
    sibling = el.find_next_sibling()
    if sibling:
        content = sibling.get_text(strip=True)
        if content:
            return content

    # Strategy 3: Next <p> in DOM (for headings like strong/b)
    if el.name in ("strong", "b"):
        next_p = el.find_next("p")
        if next_p:
            content = next_p.get_text(strip=True)
            if content:
                return content

    # Strategy 4: Parent's text after the label (for non-inline elements)
    if el.name not in ("strong", "b") and el.parent:
        parent_text = el.parent.get_text(strip=True)
        el_text = el.get_text(strip=True)
        idx = parent_text.find(el_text)
        if idx >= 0:
            after = parent_text[idx + len(el_text):].strip()
            if after:
                return after

    # Strategy 5: Walk up to an accordion/container parent and find <p> content
    # (handles structures like Boticário where h3 is nested deep inside buttons/labels)
    ancestor = el.parent
    for _ in range(5):  # max 5 levels up
        if ancestor is None:
            break
        classes = " ".join(ancestor.get("class", []))
        if re.search(r"accordion.*padding|container.*padding|accordion-pdp", classes):
            for p in ancestor.find_all("p"):
                p_text = p.get_text(strip=True)
                if p_text and len(p_text) > 20 and p_text != el.get_text(strip=True):
                    return p_text
            break
        ancestor = ancestor.parent

    return None


def extract_sections_from_html(
    html: str,
    section_label_map: dict,
) -> SectionExtractionResult:
    """Extract page sections classified into taxonomy fields.

    Args:
        html: Raw HTML string
        section_label_map: Dict mapping taxonomy field names to config with 'labels' list
            and optional 'validators' list.

    Returns:
        SectionExtractionResult with classified content.
    """
    soup = _get_soup(html)
    result = SectionExtractionResult()

    # Build a flat lookup: normalized_label -> (taxonomy_field, original_label, validators)
    label_lookup: list[tuple[str, str, str, list[str]]] = []
    for taxonomy_field, config in section_label_map.items():
        validators = config.get("validators", [])
        for label in config.get("labels", []):
            normalized = _normalize_label(label)
            label_lookup.append((normalized, taxonomy_field, label, validators))

    # Sort by label length descending so more specific labels match first
    label_lookup.sort(key=lambda x: len(x[0]), reverse=True)

    # Find heading-like elements
    for el in soup.find_all(HEADING_TAGS):
        el_text = el.get_text(strip=True)
        if not el_text:
            continue
        el_normalized = _normalize_label(el_text)

        for norm_label, taxonomy_field, original_label, validators in label_lookup:
            if not el_normalized.startswith(norm_label):
                continue

            content = _extract_content_after_heading(el)
            if not content:
                break

            actual_field = taxonomy_field

            # For ingredients_inci, validate the content
            if taxonomy_field == "ingredients_inci":
                if validate_inci_content(content):
                    actual_field = "ingredients_inci"
                else:
                    # Reclassify to composition if INCI validation fails
                    actual_field = "composition"

            # Promote composition -> ingredients_inci when content looks like INCI
            # This handles cases where "composição" label is shared between
            # composition and ingredients_inci in the blueprint, and the
            # composition entry wins the label_lookup sort order.
            if taxonomy_field == "composition" and validate_inci_content(content):
                actual_field = "ingredients_inci"

            section = PageSection(
                label=norm_label,
                content=content,
                selector=f"{el.name}:{el_text}",
                element_tag=el.name,
                taxonomy_field=actual_field,
                source_section_label=el_text,
            )
            result.sections.append(section)

            # Assign to result fields (first match wins per field)
            if actual_field == "description" and result.description is None:
                result.description = content
            elif actual_field == "care_usage" and result.care_usage is None:
                result.care_usage = content
            elif actual_field == "composition" and result.composition is None:
                result.composition = content
            elif actual_field == "ingredients_inci" and result.ingredients_inci_raw is None:
                result.ingredients_inci_raw = content

            break  # Only match the first (most specific) label per heading

    # Strategy 2: Table-based sections (e.g., Nuvemshop stores with label|content table rows)
    # First column is the section label, second column is the content
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        label_text = tds[0].get_text(strip=True)
        if not label_text:
            continue
        label_normalized = _normalize_label(label_text)

        for norm_label, taxonomy_field, original_label, validators in label_lookup:
            if not label_normalized.startswith(norm_label):
                continue

            content = tds[-1].get_text(strip=True)
            if not content:
                break

            actual_field = taxonomy_field

            if taxonomy_field == "ingredients_inci":
                if validate_inci_content(content):
                    actual_field = "ingredients_inci"
                else:
                    actual_field = "composition"

            if taxonomy_field == "composition" and validate_inci_content(content):
                actual_field = "ingredients_inci"

            section = PageSection(
                label=norm_label,
                content=content,
                selector=f"table td:{label_text}",
                element_tag="td",
                taxonomy_field=actual_field,
                source_section_label=label_text,
            )
            result.sections.append(section)

            if actual_field == "description" and result.description is None:
                result.description = content
            elif actual_field == "care_usage" and result.care_usage is None:
                result.care_usage = content
            elif actual_field == "composition" and result.composition is None:
                result.composition = content
            elif actual_field == "ingredients_inci" and result.ingredients_inci_raw is None:
                result.ingredients_inci_raw = content

            break

    return result
