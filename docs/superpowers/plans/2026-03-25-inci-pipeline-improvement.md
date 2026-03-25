# INCI Pipeline Improvement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve INCI extraction rate from 40% to 55%+ by fixing the validator, extraction heuristics, and enabling LLM fallback broadly.

**Architecture:** Audit-driven bottom-up approach. First add `inci_source` metadata to track where INCI came from. Then relax validation conditionally (only when section context exists). Then improve extraction patterns. Then enable LLM fallback and re-scrape.

**Tech Stack:** Python 3.12, Click CLI, SQLAlchemy, BeautifulSoup4, regex, pytest

**Spec:** `docs/superpowers/specs/2026-03-24-inci-improvement-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/extraction/deterministic.py` | Modify | Add `inci_source` to return dict, new tab strategies |
| `src/extraction/inci_extractor.py` | Modify | Add `\n` separator, `has_section_context` param, bilingual strip |
| `src/core/inci_validator.py` | Modify | Contextual min ingredients, skip verb check with context |
| `src/extraction/section_classifier.py` | Modify | Anchor-ingredient reclassification |
| `src/pipeline/coverage_engine.py` | Modify | Thread `inci_source`/`has_section_context`, refine LLM prompt |
| `src/core/models.py` | Modify | Add `has_section_context` attr to `ProductExtraction` |
| `src/core/qa_gate.py` | Modify | Accept `has_section_context` in `run_product_qa()` |
| `src/cli/main.py` | Modify | Add `audit-inci` command |
| `tests/extraction/test_inci_extractor.py` | Modify | Tests for new separator, bilingual, context flag |
| `tests/core/test_inci_validator.py` | Modify | Tests for contextual validation |
| `tests/extraction/test_section_classifier.py` | Modify | Tests for anchor reclassification |
| `tests/core/test_qa_gate.py` | Modify | Tests for context-aware QA |
| `config/blueprints/*.yaml` | Modify | Enable `use_llm_fallback: true` on 7 brands |

---

### Task 1: Audit Express — CLI Command

**Files:**
- Modify: `src/cli/main.py:260` (add command after existing `audit`)
- Read: `src/storage/repository.py` (query methods)

- [ ] **Step 1: Add `audit-inci` CLI command**

```python
@cli.command(name="audit-inci")
@click.option("--brand", default=None, help="Filter by brand slug (omit for all brands)")
def audit_inci(brand: str | None):
    """Audit INCI extraction coverage and classify failure types."""
    from src.storage.database import get_engine
    from src.storage.orm_models import Base, ProductORM
    from sqlalchemy.orm import Session as SASession
    from collections import defaultdict

    engine = get_engine()
    Base.metadata.create_all(engine)

    with SASession(engine) as session:
        query = session.query(ProductORM)
        if brand:
            query = query.filter(ProductORM.brand_slug == brand)
        products = query.all()

        categories = {
            "already_verified": [],
            "extracted_rejected": [],
            "extraction_missed": [],
            "no_inci_on_page": [],
        }

        for p in products:
            if p.verification_status == "verified_inci" and p.inci_ingredients:
                categories["already_verified"].append(p)
            elif p.inci_ingredients:
                # Has INCI but not verified — validator rejected
                categories["extracted_rejected"].append(p)
            elif p.composition:
                # Has composition text but no INCI — extraction missed
                categories["extraction_missed"].append(p)
            else:
                categories["no_inci_on_page"].append(p)

        # Group by brand + collect sample URLs
        brand_stats = defaultdict(lambda: defaultdict(int))
        brand_samples = defaultdict(lambda: defaultdict(list))
        for cat, prods in categories.items():
            for p in prods:
                brand_stats[p.brand_slug][cat] += 1
                if len(brand_samples[p.brand_slug][cat]) < 3:
                    brand_samples[p.brand_slug][cat].append(p.product_url)

        total = len(products)
        click.echo(f"\n{'='*60}")
        click.echo(f"INCI AUDIT — {total} products")
        click.echo(f"{'='*60}\n")

        for cat, prods in categories.items():
            pct = len(prods) / total * 100 if total else 0
            click.echo(f"  {cat}: {len(prods)} ({pct:.1f}%)")

        # Recoverable products summary
        recoverable = len(categories["extracted_rejected"]) + len(categories["extraction_missed"])
        click.echo(f"\n  Recoverable (validator fix + extraction fix): {recoverable}")

        click.echo(f"\n{'─'*60}")
        click.echo("Per brand:\n")

        for b_slug in sorted(brand_stats.keys()):
            stats = brand_stats[b_slug]
            b_total = sum(stats.values())
            click.echo(f"  {b_slug} ({b_total} products):")
            for cat in ["already_verified", "extracted_rejected", "extraction_missed", "no_inci_on_page"]:
                count = stats.get(cat, 0)
                pct = count / b_total * 100 if b_total else 0
                click.echo(f"    {cat}: {count} ({pct:.0f}%)")
                # Show sample URLs for actionable categories
                if cat != "already_verified":
                    for url in brand_samples[b_slug].get(cat, []):
                        click.echo(f"      -> {url}")
            click.echo()
```

- [ ] **Step 2: Run audit to get baseline**

Run: `haira audit-inci`
Expected: Report showing categories per brand. Save output for before/after comparison.

- [ ] **Step 3: Commit**

```bash
git add src/cli/main.py
git commit -m "feat: add audit-inci CLI command for INCI coverage diagnostics"
```

---

### Task 2: Add `inci_source` to Deterministic Extractor

**Files:**
- Modify: `src/extraction/deterministic.py:313-324` (return dict)
- Test: `tests/extraction/test_deterministic.py`

- [ ] **Step 1: Write test for `inci_source` field**

Add to `tests/extraction/test_deterministic.py`:

```python
def test_inci_source_from_section_classifier():
    """When INCI comes from section classifier, inci_source should be 'section_classifier'."""
    html = """<html><body>
    <h2>Ingredientes</h2>
    <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum</p>
    </body></html>"""
    result = extract_product_deterministic(
        html, "https://example.com/product",
        section_label_map={"ingredients_inci": {"labels": ["ingredientes"], "validators": ["has_separators", "min_length_30"]}}
    )
    assert result.get("inci_source") in ("section_classifier", "tab_label_heuristic", "css_selector")


def test_inci_source_absent_when_no_inci():
    """When no INCI is extracted, inci_source should be None."""
    html = "<html><body><h1>Product</h1><p>No ingredients here</p></body></html>"
    result = extract_product_deterministic(html, "https://example.com/product")
    assert result.get("inci_source") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/extraction/test_deterministic.py -k "inci_source" -v`
Expected: FAIL — `inci_source` key not in result dict.

- [ ] **Step 3: Add `inci_source` to return dict in `deterministic.py`**

In `extract_product_deterministic()` (line ~313), add `"inci_source": None` to the initial result dict. Then set it at each extraction point:

- After section classifier extraction (line ~373): `result["inci_source"] = "section_classifier"`
- After CSS selector extraction (line ~407): `result["inci_source"] = "css_selector"`
- After tab label heuristic (around the `_extract_inci_by_tab_labels` call): `result["inci_source"] = "tab_label_heuristic"`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/extraction/test_deterministic.py -k "inci_source" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/extraction/deterministic.py tests/extraction/test_deterministic.py
git commit -m "feat: add inci_source field to deterministic extraction result"
```

---

### Task 3: Contextual Validator — `has_section_context` Flag

**Files:**
- Modify: `src/extraction/inci_extractor.py:25-34`
- Modify: `src/core/inci_validator.py:94-126`
- Test: `tests/core/test_inci_validator.py`
- Test: `tests/extraction/test_inci_extractor.py`

- [ ] **Step 1: Write tests for contextual validation**

Add to `tests/core/test_inci_validator.py`:

```python
def test_3_ingredients_rejected_without_context():
    """3 ingredients should be rejected without section context (min 5)."""
    result = validate_inci_list(["Aqua", "Sodium Laureth Sulfate", "Glycerin"])
    assert not result.valid


def test_3_ingredients_accepted_with_context():
    """3 ingredients should be accepted with section context (min 3)."""
    result = validate_inci_list(
        ["Aqua", "Sodium Laureth Sulfate", "Glycerin"],
        has_section_context=True
    )
    assert result.valid


def test_portuguese_verb_rejected_without_context():
    """Ingredient containing verb should be rejected without context."""
    result = validate_inci_list(
        ["Aqua", "Sodium Laureth Sulfate", "Glycerin", "aplique no cabelo", "Parfum"]
    )
    # "aplique" is a verb indicator — ingredient should be removed
    assert "aplique no cabelo" not in result.cleaned


def test_verb_ingredient_kept_with_context():
    """With section context, verb check is relaxed — ingredient with verb word is kept."""
    result = validate_inci_list(
        ["Aqua", "Sodium Laureth Sulfate", "Glycerin", "aplique no cabelo", "Parfum"],
        has_section_context=True
    )
    # With context, verb check is skipped so "aplique no cabelo" is kept
    assert "aplique no cabelo" in result.cleaned
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_inci_validator.py -k "context" -v`
Expected: FAIL — `has_section_context` parameter not recognized.

- [ ] **Step 3: Implement `has_section_context` in `validate_inci_list()`**

In `src/core/inci_validator.py`, modify `validate_inci_list()` (line 94):

```python
def validate_inci_list(
    ingredients: list[str],
    has_section_context: bool = False,
) -> INCIValidationResult:
```

Changes inside the function:
- Min ingredients: `min_count = 3 if has_section_context else 5`
- Pass `has_section_context` to `validate_ingredient()` calls
- In `validate_ingredient()` (line 54): add `has_section_context: bool = False` param. Skip `VERB_INDICATORS` check when `has_section_context=True`.

- [ ] **Step 4: Thread flag through `inci_extractor.py`**

In `src/extraction/inci_extractor.py`, modify `extract_and_validate_inci()` (line 25):

```python
def extract_and_validate_inci(
    raw_text: str | None,
    has_section_context: bool = False,
) -> INCIValidationResult:
```

Pass `has_section_context` to `validate_inci_list()` call inside.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/core/test_inci_validator.py -k "context" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/core/inci_validator.py src/extraction/inci_extractor.py tests/core/test_inci_validator.py
git commit -m "feat: add has_section_context flag for contextual INCI validation"
```

---

### Task 4: Newline Separator + Bilingual Format

**Files:**
- Modify: `src/extraction/inci_extractor.py:9,12-22,25-34`
- Test: `tests/extraction/test_inci_extractor.py`

- [ ] **Step 1: Write tests**

Add to `tests/extraction/test_inci_extractor.py`:

```python
def test_newline_separated_inci():
    """INCI list separated by newlines should be split correctly."""
    raw = "Aqua\nSodium Laureth Sulfate\nCocamidopropyl Betaine\nGlycerin\nParfum"
    result = extract_and_validate_inci(raw, has_section_context=True)
    assert result.valid
    assert len(result.cleaned) >= 5


def test_bilingual_parenthetical_stripped():
    """Parenthetical translations should be stripped before validation."""
    raw = "Aqua (Agua), Sodium Laureth Sulfate (Sulfato de Sodio), Glycerin (Glicerina), Cocamidopropyl Betaine, Parfum"
    result = extract_and_validate_inci(raw, has_section_context=True)
    assert result.valid
    # Original INCI names should remain, not Portuguese translations
    assert "Aqua" in result.cleaned


def test_bilingual_preserves_short_parens():
    """Short parentheticals like (and) should NOT be stripped."""
    raw = "PEG-40 Hydrogenated Castor Oil (and) Polysorbate 20, Aqua, Glycerin, Parfum, Sodium Chloride"
    result = extract_and_validate_inci(raw, has_section_context=True)
    assert any("(and)" in ing for ing in result.cleaned)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/extraction/test_inci_extractor.py -k "newline or bilingual" -v`
Expected: FAIL

- [ ] **Step 3: Add newline to `_split_ingredients()`**

In `src/extraction/inci_extractor.py`:

Update `INCI_SEPARATORS` (line 9) to include `\n`:
```python
INCI_SEPARATORS = re.compile(r"[,;●•·|/]\s*|\s{2,}|\n+")
```

In `_split_ingredients()` (line 12), add newline priority before comma: if `\n` appears in text and would produce 3+ terms, use newline split.

- [ ] **Step 4: Add bilingual pre-processing**

In `extract_and_validate_inci()`, add before splitting:

```python
import re
# Strip parenthetical translations for validation only.
# Only strip if parenthetical contains a space (translations are multi-word).
# This preserves legitimate INCI parentheticals like (CI 77891), (Vitamin E), (Retinol).
# Single-word parens are kept; multi-word 4-50 char parens with spaces are stripped.
BILINGUAL_PATTERN = re.compile(r"\s*\([^)]{4,50}?\)")

def _strip_bilingual_parens(text: str) -> str:
    """Strip parenthetical translations (multi-word, 4-50 chars) but keep INCI-standard parens."""
    def _should_strip(match):
        content = match.group(0).strip()
        inner = content[1:-1].strip()  # remove ( and )
        # Only strip if it contains a space (translations are multi-word)
        # and does NOT look like an INCI identifier (CI, Vitamin, etc.)
        if " " not in inner:
            return match.group(0)  # keep single-word parens
        inci_prefixes = ("ci ", "vitamin", "retinol", "tocopherol")
        if inner.lower().startswith(inci_prefixes):
            return match.group(0)  # keep INCI-standard parens
        return ""  # strip translation
    return BILINGUAL_PATTERN.sub(_should_strip, text)

cleaned_for_validation = _strip_bilingual_parens(raw_text) if raw_text else raw_text
```

Use `cleaned_for_validation` for splitting and validation. Store original `raw_text` in evidence.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/extraction/test_inci_extractor.py -k "newline or bilingual" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/extraction/inci_extractor.py tests/extraction/test_inci_extractor.py
git commit -m "feat: add newline separator and bilingual parenthetical stripping for INCI"
```

---

### Task 5: Anchor-Ingredient Reclassification

**Files:**
- Modify: `src/extraction/section_classifier.py:218-233`
- Test: `tests/extraction/test_section_classifier.py`

- [ ] **Step 1: Write test**

Add to `tests/extraction/test_section_classifier.py`:

```python
def test_composition_with_verbs_promoted_via_anchors():
    """Composition section that FAILS validate_inci_content (has marketing verbs)
    but HAS anchor INCI ingredients should still be promoted to ingredients_inci."""
    # This content has "descubra" (a marketing verb) mixed in, so validate_inci_content() rejects it.
    # But anchor ingredients (aqua, sodium, glycerin, dimethicone) should trigger promotion.
    html = """<html><body>
    <h2>Composicao</h2>
    <p>Descubra a formula: Aqua, Sodium Laureth Sulfate, Glycerin, Parfum, Dimethicone, Cetearyl Alcohol</p>
    </body></html>"""
    section_map = {
        "composition": {"labels": ["composicao"]},
    }
    result = extract_sections_from_html(html, section_map)
    assert result.ingredients_inci_raw is not None
    assert "Aqua" in result.ingredients_inci_raw
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/extraction/test_section_classifier.py -k "anchor" -v`
Expected: FAIL — composition not promoted (current validator rejects it or reclassification doesn't trigger).

- [ ] **Step 3: Add anchor ingredient list and reclassification logic**

In `src/extraction/section_classifier.py`, add near the top:

```python
INCI_ANCHOR_INGREDIENTS = {
    "aqua", "water", "sodium", "glycerin", "cetearyl", "dimethicone",
    "parfum", "tocopherol", "phenoxyethanol", "behentrimonium",
    "stearyl", "cetyl", "isopropyl", "polyquaternium", "panthenol",
    "cocamidopropyl", "laureth", "amodimethicone", "fragrance", "citric",
}
```

**Two changes needed:**

**5a.** Add `has_section_context` param to `validate_inci_content()` (line 74):

```python
def validate_inci_content(text: str | None, has_section_context: bool = False) -> bool:
```

When `has_section_context=True`, skip the `ALL_REJECTION_VERBS` check (line ~86-90). This addresses the spec's Section 2c requirement that BOTH verb check locations are relaxed.

Update all callers of `validate_inci_content` in section_classifier.py to pass context when available (reclassification calls at lines ~222, ~232 can pass `True` since content comes from a labeled section).

**5b.** In the reclassification block (line ~228-233), add anchor-ingredient alternative promotion path:

```python
# Existing check: validate_inci_content(content)
# New alternative: anchor ingredient check when validate_inci_content fails
if not validate_inci_content(content, has_section_context=True):
    words = {w.lower().strip(",.;") for w in content.split()}
    anchor_matches = words & INCI_ANCHOR_INGREDIENTS
    if len(anchor_matches) >= 3:
        # Promote: enough anchor ingredients to signal INCI
        # (proceed with promotion to ingredients_inci)
```

Note: `INCI_ANCHOR_INGREDIENTS` uses single words for matching. Multi-word anchors from the spec like "Citric Acid" should be split: include `"citric"` (single word is sufficient since "citric" alone is unambiguous in INCI context).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/extraction/test_section_classifier.py -k "anchor" -v`
Expected: PASS

- [ ] **Step 5: Run full section_classifier test suite for regression**

Run: `pytest tests/extraction/test_section_classifier.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/extraction/section_classifier.py tests/extraction/test_section_classifier.py
git commit -m "feat: add anchor-ingredient reclassification for composition->INCI promotion"
```

---

### Task 6: New Tab/Accordion Strategies in Deterministic Extractor

**Files:**
- Modify: `src/extraction/deterministic.py:93-210`
- Test: `tests/extraction/test_deterministic.py`

- [ ] **Step 1: Write tests**

Add to `tests/extraction/test_deterministic.py`:

```python
def test_details_summary_inci_extraction():
    """INCI inside <details>/<summary> should be extracted."""
    html = """<html><body>
    <details>
        <summary>Ingredientes</summary>
        <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum</p>
    </details>
    </body></html>"""
    result = extract_product_deterministic(html, "https://example.com/product")
    assert result.get("inci_raw") is not None
    assert "Aqua" in result["inci_raw"]


def test_data_attribute_tab_inci_extraction():
    """INCI inside data-attribute tab content should be extracted."""
    html = """<html><body>
    <div data-tab="ingredientes">
        <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum</p>
    </div>
    </body></html>"""
    result = extract_product_deterministic(html, "https://example.com/product")
    assert result.get("inci_raw") is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/extraction/test_deterministic.py -k "details or data_attribute" -v`
Expected: FAIL

- [ ] **Step 3: Add strategies to `_extract_inci_by_tab_labels()`**

In `src/extraction/deterministic.py`, add after existing Strategy 2 (~line 203):

```python
# Strategy 3: <details>/<summary> pattern
for details in soup.find_all("details"):
    summary = details.find("summary")
    if summary:
        summary_text = summary.get_text(strip=True).lower()
        for label in INCI_TAB_LABELS:
            if label in summary_text:
                content_parts = []
                for child in details.children:
                    if child != summary and hasattr(child, "get_text"):
                        content_parts.append(child.get_text(strip=True))
                content = " ".join(content_parts).strip()
                if content and len(content) >= 30:
                    return content, f"details_summary:{label}"

# Strategy 4: data-* attribute patterns
for attr in ["data-tab", "data-content", "data-accordion", "data-panel"]:
    for el in soup.find_all(attrs={attr: True}):
        attr_val = el.get(attr, "").lower()
        for label in INCI_TAB_LABELS:
            if label in attr_val:
                content = el.get_text(strip=True)
                if content and len(content) >= 30:
                    return content, f"data_attr:{attr}:{label}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/extraction/test_deterministic.py -k "details or data_attribute" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/extraction/deterministic.py tests/extraction/test_deterministic.py
git commit -m "feat: add details/summary and data-attribute tab strategies for INCI extraction"
```

---

### Task 7: Thread Context Through Coverage Engine + QA Gate

**Files:**
- Modify: `src/pipeline/coverage_engine.py:204-229`
- Modify: `src/core/qa_gate.py:33,89`
- Test: `tests/core/test_qa_gate.py`

- [ ] **Step 1: Write test for QA gate with context**

Add to `tests/core/test_qa_gate.py`:

```python
def test_3_ingredient_product_passes_with_section_context():
    """Product with 3 INCI ingredients should pass QA when has_section_context=True."""
    product = ProductExtraction(
        brand_slug="test",
        product_name="Test Shampoo",
        product_url="https://example.com/test",
        inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Glycerin"],
        confidence=0.90,
        extraction_method="deterministic",
    )
    result = run_product_qa(
        product,
        allowed_domains=["example.com"],
        has_section_context=True,
    )
    assert result.status.value == "verified_inci"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_qa_gate.py -k "section_context" -v`
Expected: FAIL — `has_section_context` not accepted by `run_product_qa()`.

- [ ] **Step 3: Add `has_section_context` to `run_product_qa()` and thread through**

In `src/core/qa_gate.py`:

```python
def run_product_qa(
    product: ProductExtraction,
    allowed_domains: list[str],
    config: QAConfig | None = None,
    has_section_context: bool = False,
) -> QAResult:
```

At line ~89 where `validate_inci_list()` is called:
```python
inci_result = validate_inci_list(product.inci_ingredients, has_section_context=has_section_context)
```

- [ ] **Step 4: Thread in `coverage_engine.py`**

In `_extract_product()` (line ~205):

```python
inci_source = det_result.get("inci_source")
has_section_context = inci_source in ("section_classifier", "tab_label_heuristic")

inci_result = extract_and_validate_inci(inci_raw, has_section_context=has_section_context)
```

**IMPORTANT:** `run_product_qa()` is called from `process_brand()`, NOT from `_extract_product()`. So `_extract_product()` must return `has_section_context` alongside the `ProductExtraction`. Two options:

Option A (recommended): Add `has_section_context` as an attribute on `ProductExtraction` model in `src/core/models.py`. Set it in `_extract_product()`. Then `process_brand()` reads it when calling QA:

```python
# In _extract_product(), after building ProductExtraction:
product.has_section_context = has_section_context

# In process_brand(), where run_product_qa is called:
qa_result = run_product_qa(
    product, allowed_domains,
    has_section_context=getattr(product, "has_section_context", False)
)
```

Option B: Return a tuple `(product, has_section_context)` from `_extract_product()` and unpack in `process_brand()`.

Use Option A — it requires fewer signature changes.

- [ ] **Step 5: Run tests**

Run: `pytest tests/core/test_qa_gate.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite for regression**

Run: `pytest -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/pipeline/coverage_engine.py src/core/qa_gate.py tests/core/test_qa_gate.py
git commit -m "feat: thread has_section_context through coverage engine and QA gate"
```

---

### Task 8: LLM Fallback — Enable + Refine Prompt

**Files:**
- Modify: `src/pipeline/coverage_engine.py:135-142` (LLM prompt)
- Modify: `config/blueprints/haskell.yaml`, `redken.yaml`, `wella.yaml`, `all-nature.yaml`, `amend.yaml`, `widi-care.yaml`, `griffus.yaml`

- [ ] **Step 1: Refine LLM prompt in `_try_llm_extraction()`**

In `src/pipeline/coverage_engine.py`, update the prompt at line ~135:

```python
prompt = f"""Extract product data from this page text.

Return JSON with:
- "inci_ingredients": list of ingredients (ONLY if you find a complete ingredient list)
- "description": product description string
- "separator": the separator character used between ingredients (e.g. ",", ";", "/")

Rules:
- Accept ingredient names in Portuguese (e.g. "sulfato de sodio laurete") as well as standard INCI names
- Ignore marketing text, usage instructions, and benefits — only extract the actual ingredient list
- Do NOT guess or infer ingredients. Only extract what is explicitly listed.
- A complete list typically starts with "Aqua" or "Water" and contains 5+ ingredients

Product: {product_name}
"""
```

Note: The `separator` field in the LLM response is informational for debugging. The `_try_llm_extraction()` result parsing does not need to change — `inci_ingredients` list is already consumed correctly. Log the separator if present for future analysis.

- [ ] **Step 2: Enable `use_llm_fallback` in 7 brand blueprints**

For each of these files in `config/blueprints/`, ensure `use_llm_fallback: true` is set:
- `haskell.yaml`
- `redken.yaml`
- `wella.yaml`
- `all-nature.yaml`
- `amend.yaml`
- `widi-care.yaml`
- `griffus.yaml`

- [ ] **Step 3: Commit**

```bash
git add src/pipeline/coverage_engine.py config/blueprints/
git commit -m "feat: refine LLM prompt and enable fallback for 7 medium-INCI brands"
```

---

### Task 9: Re-scrape + Measure Results

**Files:**
- Run: CLI commands only

- [ ] **Step 1: Snapshot baseline**

Run: `haira audit-inci > /tmp/inci-audit-before.txt`

- [ ] **Step 2: Re-scrape medium brands**

Run each sequentially:
```bash
haira scrape --brand haskell
haira scrape --brand redken
haira scrape --brand wella
haira scrape --brand all-nature
haira scrape --brand amend
haira scrape --brand widi-care
haira scrape --brand griffus
```

- [ ] **Step 3: Run labels on re-scraped brands**

Re-scrape changes INCI data, which invalidates cached label results (sulfate_free, vegan, etc. are computed from INCI). Must re-run labels to recalculate.

```bash
haira labels --brand haskell
haira labels --brand redken
haira labels --brand wella
haira labels --brand all-nature
haira labels --brand amend
haira labels --brand widi-care
haira labels --brand griffus
```

- [ ] **Step 4: Run audit again and compare**

Run: `haira audit-inci > /tmp/inci-audit-after.txt`
Compare: `diff /tmp/inci-audit-before.txt /tmp/inci-audit-after.txt`

Expected: INCI rate improvement of 15+ percentage points on average for medium brands.

- [ ] **Step 5: Spot-check for false positives**

Manually check 5 random products per brand that changed from `catalog_only` to `verified_inci`. Verify the INCI list is real, not marketing text.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: inci pipeline improvement - re-scrape results for medium brands"
```
