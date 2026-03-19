# HAIRA v2 — Selos Inteligentes (Smart Labels) Design

**Date:** 2026-02-26
**Status:** Approved
**Focus:** Brand Amend first, then scale to 700+ brands

## Context

The HAIRA v2 scraping pipeline is functional with 706 brands registered and ~1000 products extracted.
Current gap: no structured system for product quality/claim badges (seals).

New requirement: create a structured `product_labels` system with rule-based detection,
INCI inference, and full auditability.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pipeline integration | Post-processing CLI command | Iterate on rules without re-scraping; Amend already has 93 products in DB |
| Detection methods | Text keywords + INCI inference | Covers ~80% of cases; OCR deferred until gap measured |
| Reference lists storage | YAML files in `config/labels/` | Follows project pattern (blueprints); editable without code changes |
| DB storage | Hybrid: JSON column + product_evidence rows | Fast reads via JSON; auditability via existing evidence system |

## Supported Seals (v1)

15 seals, English-standardized backend names:

- `sulfate_free`
- `paraben_free`
- `silicone_free`
- `fragrance_free`
- `vegan`
- `cruelty_free`
- `organic`
- `natural`
- `hypoallergenic`
- `dermatologically_tested`
- `ophthalmologically_tested`
- `uv_protection`
- `thermal_protection`
- `low_poo`
- `no_poo`

## Detection Methods

### Method 1: Keyword Matching (official text)

Scans `description`, `product_name`, `benefits_claims`, `usage_instructions`.
Uses multilingual keyword dictionary from `config/labels/seals.yaml`.

Match found → added to `detected[]`, source: `official_text`

### Method 2: INCI Inference (ingredient analysis)

Compares `inci_ingredients` against prohibited ingredient lists:

- `config/labels/silicones.yaml` — ~30 common silicones
- `config/labels/surfactants.yaml` — prohibited surfactants for low_poo/no_poo

No prohibited ingredient found + verified INCI → added to `inferred[]`, source: `inci_analysis`

**Critical rule:** No evidence = empty field. Never fabricate a seal.

## Schema

New JSON column on `products` table:

```json
{
  "detected": ["sulfate_free", "vegan"],
  "inferred": ["silicone_free"],
  "confidence": 0.85,
  "sources": ["official_text", "inci_analysis"],
  "manually_verified": false,
  "manually_overridden": false
}
```

Each seal also generates a row in `product_evidence`:

- `field_name`: `"label:sulfate_free"`
- `extraction_method`: `"text_keyword"` or `"inci_inference"`
- `raw_source_text`: matched text or analysis summary
- `evidence_locator`: field where evidence was found

## Confidence Scoring

| Score | Condition |
|-------|-----------|
| 0.0 | No seals found (field empty/null) |
| 0.5 | Only inferred (no textual confirmation) |
| 0.8 | Only detected (official text) |
| 0.9 | Both detected and inferred agree |
| 1.0 | manually_verified = true |

## CLI Interface

```bash
haira labels --brand amend              # process all products
haira labels --brand amend --limit 10   # test with 10 products
haira labels --brand amend --dry-run    # show results without saving
```

## New Files

```
config/labels/
  seals.yaml              # 15 seals + multilingual keywords
  silicones.yaml          # ~30 prohibited silicones
  surfactants.yaml        # prohibited surfactants (low_poo/no_poo)

src/core/label_engine.py  # LabelEngine class (detect + infer + score)
src/cli/labels.py         # CLI command registration

migrations/               # Alembic migration for product_labels column
```

## Workflow for Amend

1. Run `haira labels --brand amend --dry-run` on 93 existing products
2. Review output — validate detected seals vs actual site
3. Adjust keywords/lists as needed
4. Run `haira labels --brand amend` to persist
5. Generate precision report

## Out of Scope (for now)

- Image OCR (add later if coverage gap justifies cost)
- API endpoint for manual seal editing
- Seal visualization in dashboard
- QA Gate blocking by seal score
