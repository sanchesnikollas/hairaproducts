# INCI Pipeline Improvement — Design Spec

**Date:** 2026-03-24
**Goal:** Melhorar taxa INCI do pipeline HAIRA (hoje 40%) via melhorias no validador, extração e LLM fallback.
**Approach:** Audit-driven bottom-up — diagnosticar primeiro, corrigir onde o dado mostra ganho, habilitar LLM amplo.
**Risk posture:** Balanceado — relaxar validação só com contexto de seção; manter conservador sem contexto.

---

## Section 1: Audit Express

### What
Comando CLI `haira audit-inci` que analisa dados já no DB e classifica cada produto por tipo de falha INCI.

### Categories
| Category | Meaning | Action |
|----------|---------|--------|
| `extracted_rejected` | INCI extraído (em `product_evidence`) mas validador rejeitou | Fix validador |
| `extraction_missed` | Página tem seção "ingredientes"/"composição" mas INCI não capturado | Fix extração |
| `no_inci_on_page` | Nenhuma evidência de ingredientes na página | LLM fallback |
| `already_verified` | INCI válido presente | Nenhuma |

### Output
- Relatório por marca: contagem por categoria + % do total.
- Top 3 URLs de exemplo por categoria por marca (para debug manual).
- Summary: total de produtos recuperáveis por tipo de fix.

### Implementation
- Query em `product_evidence` (field_name contendo "inci" ou "composition") + `products` (status).
- `extraction_missed` detection: check if `ProductORM.composition` field is populated (proxy for "page had ingredient-like content") but `ingredients_inci` is NULL. This avoids re-fetching pages.
- Sem requests HTTP, sem re-scrape. Roda em segundos.
- Novo comando em `src/cli/main.py` via Click.

---

## Section 2: Fix Validador

### Files affected
- `src/extraction/inci_extractor.py` — `_split_ingredients()`, `extract_and_validate_inci()`
- `src/core/inci_validator.py` — `validate_inci_list()`

### 2a. Separadores adicionais
- `INCI_SEPARATORS` regex already includes `/`, `|`, and bullet chars. The actual gap is `\n` (newline as separator).
- Add `\n` to recognized separators in `_split_ingredients()`.
- Refine priority order: bullets > `\n` > `;` > `,` (extends existing logic).

### 2b. Minimum ingredients contextual
- New parameter `has_section_context: bool` passed from extractor to validator.
- If `has_section_context=True` (INCI came from labeled section): accept 3+ ingredients.
- If `has_section_context=False` (generic selector/fallback): keep 5 minimum.
- Requires threading the flag through `extract_and_validate_inci()`.
- **Propagation path:** Add `inci_source` field to dict returned by `extract_product_deterministic()` with values `"section_classifier"`, `"css_selector"`, `"tab_label_heuristic"`. Then `coverage_engine.py` sets `has_section_context = det_result.get("inci_source") in ("section_classifier", "tab_label_heuristic")` before calling `extract_and_validate_inci()`.
- **QA gate alignment:** `qa_gate.py` calls `validate_inci_list()` a second time (line ~89). Must also receive `has_section_context` to avoid re-rejecting products that passed with relaxed rules. Pass it through `run_product_qa()` parameter.

### 2c. Portuguese ingredient names
- Within labeled sections (`has_section_context=True`): disable verb checks — specifically `VERB_INDICATORS` in `inci_validator.py:validate_ingredient()` (line ~63) and `ALL_REJECTION_VERBS` in `section_classifier.py:validate_inci_content()` (line ~74). These are two separate validation points with different verb lists.
- Without context: keep current strict validation.
- Rationale: labeled sections provide enough signal that the content is INCI, even if ingredient names are Portuguese translations.

### 2d. Backwards compatibility
- All changes conditional on `has_section_context` flag.
- Default `has_section_context=False` preserves current behavior for all existing callers.
- Products already verified remain verified.

---

## Section 3: Fix Extraction

### Files affected
- `src/extraction/deterministic.py` — `_extract_inci_by_tab_labels()`
- `src/extraction/section_classifier.py` — `extract_sections_from_html()`

### 3a. New accordion/tab patterns
- Note: `<details>/<summary>` already exists in `section_classifier.py` as Strategy 0 in `_extract_content_after_heading()`. The addition here is for `deterministic.py:_extract_inci_by_tab_labels()` where it does NOT exist yet.
- New strategy in `_extract_inci_by_tab_labels()`: `<details>/<summary>` pattern matching INCI labels.
- New strategy in `_extract_inci_by_tab_labels()`: `data-*` attribute patterns (`data-tab`, `data-content`, `data-accordion`) common in Nuvemshop/Shopify themes.

### 3b. More aggressive reclassification
- Current: `composition` -> `ingredients_inci` only if all validators pass.
- New: if `composition` section contains separators + 3 anchor ingredients -> promote to `ingredients_inci`.
- Note: this check is independent of the 3-ingredient minimum in Section 2b. Section 2b governs validation threshold; this governs reclassification trigger. A 4-ingredient list from a labeled section passes 2b (3+ min) but would need 3 of those 4 to be anchors for 3b.
- Cross-dependency: `validate_inci_content()` in section_classifier.py is also imported by `qa_gate.py` (line ~10). Changes here affect QA gate behavior too. Must ensure the anchor-ingredient check is additive (OR with existing checks), not replacing them.
- Anchor ingredients (~20): Aqua, Water, Sodium, Glycerin, Cetearyl, Dimethicone, Parfum, Tocopherol, Citric Acid, Phenoxyethanol, Behentrimonium, Stearyl, Cetyl, Isopropyl, Polyquaternium, Panthenol, Cocamidopropyl, Laureth, PEG-, Amodimethicone.
- These are near-universal in hair products and unambiguously signal INCI content.

### 3c. Bilingual format handling
- Pre-processing step in `extract_and_validate_inci()`: strip parenthetical translations before validation.
- Pattern: `Ingredient Name (Translated Name)` -> `Ingredient Name`.
- Regex: `\s*\([^)]{4,50}\)` (only strip 4-50 char parentheticals to avoid stripping CAS numbers, short annotations, and INCI compounds like `(and)` which is 3 chars).
- Preserve original text in `product_evidence`; cleaned version used only for validation.

### 3d. No blueprint changes needed
- Improvements are generic in pipeline code. All existing blueprints benefit automatically.

---

## Section 4: LLM Fallback + Re-scrape

### 4a. Enable LLM fallback broadly
- Set `use_llm_fallback: true` in all blueprints for medium-INCI brands.
- Do not modify blueprints that already have it enabled.
- Target brands: Haskell, Redken, Wella, All Nature, Amend, Widi Care, Griffus.

### 4b. Refine LLM prompt
- Add instruction to accept Portuguese ingredient names.
- Add instruction to ignore marketing text before/after ingredient list.
- Request structured output including detected separator for consistency.
- Location: `src/pipeline/coverage_engine.py`, method `_try_llm_extraction()` (line ~135).

### 4c. Re-scrape batch
- Run `haira scrape --brand <slug>` for all 7 medium brands.
- Run `haira labels --brand <slug>` to recalculate labels with new data.
- Compare INCI rate before/after per brand.

### 4d. Execution order
1. Fix validador + fix extração (no re-scrape, immediate gain on existing DB data).
2. Enable LLM + re-scrape medium brands.
3. Final comparative report.

---

## Success Criteria
- INCI rate for medium brands (10-50%) improves by at least 15 percentage points on average.
- No regression: brands currently >50% INCI maintain their rate.
- Audit command provides clear, actionable diagnostics per brand.

## Rollback Strategy
- **Before starting:** Snapshot current INCI rates per brand via `haira audit-inci` (Section 1 output).
- **After each section:** Compare rates. If any brand's INCI rate drops OR manual spot-check reveals false positives (marketing text classified as INCI), revert changes to that section and re-run `haira labels`.
- **DB safety:** Changes to validation don't modify stored data. Re-running `haira scrape` re-extracts and re-validates. Reverting code + re-scraping restores previous state.

## Out of Scope
- External INCI sources (Anvisa, CosIng) — future phase.
- Catalog-only brands with no INCI on site — LLM can help some, but not targeted.
- Frontend changes — this is pipeline-only.
