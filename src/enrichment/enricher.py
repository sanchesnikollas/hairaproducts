"""Gold-oriented LLM enrichment: recover INCI *and* 'como usar' from a product's
own live page, for catalog products blocked from Gold by either field.

The deterministic extractor stores INCI/description but never captured a usage
field, and the marketplace cross-reference (enrich-external) tops out ~2% because
external sources are kit/variant noise. The reliable lever is re-reading the
product's own page: deterministic first, LLM fallback for whatever is still
missing. Shared by the CLI (`haira enrich`) and the admin endpoint so the same
loop powers ad-hoc runs, the API trigger, and the per-brand orchestrator.
"""
from __future__ import annotations

from typing import Any, Callable

from bs4 import BeautifulSoup

from src.core.field_validator import is_real_usage_instructions
from src.core.taxonomy import normalize_category
from src.extraction.deterministic import extract_product_deterministic
from src.extraction.description_splitter import split_description_blob
from src.extraction.inci_extractor import extract_and_validate_inci
from src.storage.orm_models import ProductORM
from src.storage.repository import ProductRepository

_EMPTY_INCI = (None, "", "[]", "null")


def _has_inci(product: ProductORM) -> bool:
    """True when the product already carries a real INCI list."""
    val = product.inci_ingredients
    if val in _EMPTY_INCI:
        return False
    if isinstance(val, list):
        return len(val) > 0
    return True


def _has_usage(product: ProductORM) -> bool:
    return bool((product.usage_instructions or "").strip())


def pick_usage(candidates: list[str | None]) -> str | None:
    """First candidate that reads like real how-to-use text (action verbs, length).

    Gated by is_real_usage_instructions so descriptions / tab-label noise never
    leak into usage_instructions. Pure + side-effect-free, so it is unit-tested.
    """
    for c in candidates:
        if is_real_usage_instructions(c):
            return c.strip()
    return None


def _page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _llm_extract(llm, page_text: str, product: ProductORM, *, want_inci: bool, want_usage: bool) -> dict | None:
    fields = []
    if want_inci:
        fields.append(
            "- inci_ingredients: list of individual INCI ingredient names (strings), or null. "
            "ONLY if a COMPLETE ingredient list is present (usually starting with 'Aqua'/'Water'). Never guess."
        )
    if want_usage:
        fields.append(
            "- usage_instructions: the 'modo de uso' / how-to-use text (how to apply the product), "
            "or null if the page has none."
        )
    fields.append("- description: product description text, or null.")
    prompt = (
        "Extract the following fields from this hair product page.\n"
        f"Product: {product.product_name}\n\n"
        "Return JSON with these fields:\n" + "\n".join(fields) +
        "\n\nIMPORTANT: extract only what is actually on the page. Do NOT invent or infer."
    )
    try:
        return llm.extract_structured(page_text=page_text, prompt=prompt, max_tokens=2048)
    except Exception:
        return None


def enrich_brand(
    session,
    brand: str,
    *,
    llm,
    browser,
    limit: int = 0,
    dry_run: bool = False,
    log: Callable[[str], None] = lambda _m: None,
) -> dict[str, Any]:
    """Re-fetch each catalog product missing INCI or usage and fill both fields.

    Returns a stats dict (counts + llm cost). Never clears existing data:
    a field is only written when currently empty and a validated value is found.
    """
    repo = ProductRepository(session)
    products = repo.get_catalog_products_missing_gold_fields(brand)
    if limit and limit > 0:
        products = products[:limit]

    stats: dict[str, Any] = {
        "brand": brand,
        "candidates": len(products),
        "processed": 0,
        "inci_found": 0,
        "usage_found": 0,
        "desc_added": 0,
        "fetch_failed": 0,
        "no_gain": 0,
        "llm_exhausted_at": None,
    }

    for i, product in enumerate(products, 1):
        if not llm.can_call:
            stats["llm_exhausted_at"] = i - 1
            log(f"LLM budget exhausted after {i - 1} products")
            break

        need_inci = not _has_inci(product)
        need_usage = not _has_usage(product)
        if not (need_inci or need_usage):
            continue

        html = None
        if browser:
            try:
                html = browser.fetch_page(product.product_url, expand_accordions=True)
            except Exception as e:  # noqa: BLE001 — per-product, keep going
                log(f"fetch failed for {product.product_url}: {e}")
        if not html or len(html) < 200:
            stats["fetch_failed"] += 1
            continue

        stats["processed"] += 1
        text = _page_text(html)

        inci_list = None
        usage_text = None

        # 1) deterministic
        det = extract_product_deterministic(html=html, url=product.product_url)
        if need_inci and det.get("inci_raw"):
            r = extract_and_validate_inci(det["inci_raw"])
            if r.valid:
                inci_list = r.cleaned
        if need_usage:
            usage_text = pick_usage([
                split_description_blob(text).get("care_usage"),
                split_description_blob(product.description).get("care_usage"),
            ])

        # 2) LLM fallback for whatever deterministic missed
        still_inci = need_inci and inci_list is None
        still_usage = need_usage and not usage_text
        if still_inci or still_usage:
            res = _llm_extract(llm, text, product, want_inci=still_inci, want_usage=still_usage)
            if res:
                if still_inci and res.get("inci_ingredients"):
                    r = extract_and_validate_inci(", ".join(res["inci_ingredients"]))
                    if r.valid:
                        inci_list = r.cleaned
                if still_usage:
                    usage_text = pick_usage([res.get("usage_instructions")])
                if not (product.description or "").strip() and res.get("description"):
                    stats["desc_added"] += 1
                    if not dry_run:
                        product.description = res["description"]

        # 3) save (never clears)
        gained = False
        if inci_list:
            stats["inci_found"] += 1
            gained = True
            if not dry_run:
                product.inci_ingredients = inci_list
                product.verification_status = "verified_inci"
                product.confidence = 0.85
                product.extraction_method = "llm_grounded"
                if not product.product_category:
                    product.product_category = normalize_category(
                        product.product_type_normalized, product.product_name
                    )
        if usage_text:
            stats["usage_found"] += 1
            gained = True
            if not dry_run:
                product.usage_instructions = usage_text
        if not gained:
            stats["no_gain"] += 1

    if not dry_run:
        session.commit()

    stats["cost"] = llm.cost_summary
    return stats
