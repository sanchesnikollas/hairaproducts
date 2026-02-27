# src/core/field_validator.py
"""
Field cross-validation engine.

Detects content placed in the wrong field — e.g. marketing text stored as
INCI ingredients, usage instructions stored as description, etc.

Each rule returns a list of FieldIssue dataclasses.  The top-level
`validate_product_fields` runs every rule and returns a combined report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class IssueSeverity(str, Enum):
    ERROR = "error"      # Data is wrong — must be fixed
    WARNING = "warning"  # Suspicious — should be reviewed
    INFO = "info"        # Minor / cosmetic


@dataclass
class FieldIssue:
    field: str
    code: str
    severity: IssueSeverity
    message: str
    details: str = ""


@dataclass
class ValidationReport:
    issues: list[FieldIssue] = field(default_factory=list)
    score: int = 100  # 0–100, starts at 100, deductions per issue

    @property
    def has_errors(self) -> bool:
        return any(i.severity == IssueSeverity.ERROR for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "field": i.field,
                    "code": i.code,
                    "severity": i.severity.value,
                    "message": i.message,
                    "details": i.details,
                }
                for i in self.issues
            ],
        }


# ── Portuguese / English marketing phrases that should never appear in INCI ──

_MARKETING_PHRASES = [
    "sem amônia", "sem amonia", "fácil de aplicar", "fácil aplicação",
    "ideal para", "indicado para", "recomendado para",
    "maior durabilidade", "cobertura dos fios", "cor vibrante",
    "brilho intenso", "brilho natural", "cabelos naturais",
    "quimicamente tratados", "concentrado protetor", "exclusivo",
    "formulação", "proporciona", "promove", "fortalece",
    "protege", "suavidade", "maciez", "hidratação profunda",
    "tecnologia", "resultado", "ação reparadora",
    "tons de", "efeito natural", "longa duração",
]

_USAGE_PHRASES = [
    "aplique", "aplicar", "aplicação", "massageie", "massage",
    "enxágue", "enxague", "rinse", "deixe agir", "aguarde",
    "espalhe", "distribua", "use em", "use nos", "use no",
    "apply to", "apply on", "spread", "leave on", "wait",
    "wash", "lavar", "modo de uso", "como usar", "how to use",
    "passo 1", "passo 2", "step 1", "step 2",
    "seque com", "penteie", "secar", "desembarace",
]

_INCI_ANCHOR_INGREDIENTS = {
    "aqua", "water", "aqua/water", "sodium laureth sulfate",
    "sodium lauryl sulfate", "cetearyl alcohol", "glycerin",
    "dimethicone", "phenoxyethanol", "tocopherol",
    "cetrimonium chloride", "stearyl alcohol", "isopropyl myristate",
    "parfum", "fragrance", "citric acid", "sodium chloride",
    "behentrimonium chloride", "amodimethicone",
}


def _lowercase_items(items: list[str] | None) -> list[str]:
    return [i.lower().strip() for i in (items or [])]


# ── Individual Rules ──


def _check_inci_is_marketing(inci: list[str] | None) -> list[FieldIssue]:
    """Detect INCI list that is actually marketing/benefits text."""
    if not inci:
        return []
    lower_items = _lowercase_items(inci)
    anchors_found = sum(1 for i in lower_items if i in _INCI_ANCHOR_INGREDIENTS)

    # If no real INCI anchor ingredients exist, check for marketing phrases
    marketing_hits = 0
    marketing_examples: list[str] = []
    for item in lower_items:
        for phrase in _MARKETING_PHRASES:
            if phrase in item:
                marketing_hits += 1
                if len(marketing_examples) < 3:
                    marketing_examples.append(item[:80])
                break

    if marketing_hits > 0 and anchors_found == 0:
        return [FieldIssue(
            field="inci_ingredients",
            code="inci_is_marketing",
            severity=IssueSeverity.ERROR,
            message=f"INCI contains marketing text instead of ingredients ({marketing_hits}/{len(inci)} items)",
            details="; ".join(marketing_examples),
        )]

    if marketing_hits > len(inci) * 0.3:
        return [FieldIssue(
            field="inci_ingredients",
            code="inci_mixed_marketing",
            severity=IssueSeverity.WARNING,
            message=f"{marketing_hits} of {len(inci)} INCI items look like marketing text",
            details="; ".join(marketing_examples),
        )]
    return []


def _check_inci_is_usage(inci: list[str] | None) -> list[FieldIssue]:
    """Detect INCI list that contains usage instructions."""
    if not inci:
        return []
    lower_items = _lowercase_items(inci)
    usage_hits = 0
    usage_examples: list[str] = []
    for item in lower_items:
        for phrase in _USAGE_PHRASES:
            if phrase in item:
                usage_hits += 1
                if len(usage_examples) < 3:
                    usage_examples.append(item[:80])
                break

    if usage_hits > len(inci) * 0.3:
        return [FieldIssue(
            field="inci_ingredients",
            code="inci_is_usage",
            severity=IssueSeverity.ERROR,
            message=f"INCI contains usage instructions ({usage_hits}/{len(inci)} items)",
            details="; ".join(usage_examples),
        )]
    if usage_hits > 0:
        return [FieldIssue(
            field="inci_ingredients",
            code="inci_has_usage_text",
            severity=IssueSeverity.WARNING,
            message=f"{usage_hits} INCI item(s) look like usage instructions",
            details="; ".join(usage_examples),
        )]
    return []


def _check_inci_has_sentences(inci: list[str] | None) -> list[FieldIssue]:
    """Detect INCI items that are full sentences (descriptions)."""
    if not inci:
        return []
    sentence_items: list[str] = []
    for item in inci:
        stripped = item.strip()
        # A sentence: has a period followed by space/uppercase, or >12 words
        if (re.search(r'\.\s+[A-Z]', stripped) and len(stripped) > 50) or len(stripped.split()) > 12:
            sentence_items.append(stripped[:80])

    if len(sentence_items) > 3:
        return [FieldIssue(
            field="inci_ingredients",
            code="inci_has_sentences",
            severity=IssueSeverity.WARNING,
            message=f"{len(sentence_items)} INCI items look like description sentences",
            details=sentence_items[0],
        )]
    return []


def _check_inci_marketing_complex(inci: list[str] | None) -> list[FieldIssue]:
    """Detect INCI items with marketing complex names appended (e.g. '*Pro-Reparage Complex: Biotin')."""
    if not inci:
        return []
    complex_items: list[str] = []
    for item in inci:
        # Patterns like: "Sodium Citrate. *Pro-Reparage Complex: Biotin"
        if re.search(r'\.\s*\*+[A-Z]', item) or re.search(r'Complex[*:\s]', item, re.IGNORECASE):
            complex_items.append(item[:80])

    if complex_items:
        return [FieldIssue(
            field="inci_ingredients",
            code="inci_marketing_complex",
            severity=IssueSeverity.INFO,
            message=f"{len(complex_items)} INCI items have marketing complex names appended",
            details=complex_items[0],
        )]
    return []


def _check_description_quality(description: str | None) -> list[FieldIssue]:
    """Validate description field content."""
    issues: list[FieldIssue] = []
    if not description or not description.strip():
        return []

    desc = description.strip()

    # Check if description looks like an INCI list
    if "," in desc:
        parts = [p.strip() for p in desc.split(",")]
        if len(parts) > 10:
            # Check if parts look like ingredients (short, no sentences)
            inci_like = sum(1 for p in parts if len(p) < 40 and len(p.split()) <= 5)
            if inci_like > len(parts) * 0.7:
                issues.append(FieldIssue(
                    field="description",
                    code="desc_is_inci_list",
                    severity=IssueSeverity.ERROR,
                    message="Description appears to be an INCI ingredient list",
                    details=desc[:120],
                ))

    # Check if description is too short to be useful
    if len(desc) < 20 and not any(c.isalpha() for c in desc):
        issues.append(FieldIssue(
            field="description",
            code="desc_too_short",
            severity=IssueSeverity.WARNING,
            message="Description is too short to be meaningful",
        ))

    return issues


def _check_usage_quality(usage: str | None) -> list[FieldIssue]:
    """Validate usage_instructions field."""
    if not usage or not usage.strip():
        return []
    text = usage.strip().lower()
    # Check if usage is actually a description (no action verbs)
    has_action_verb = any(v in text for v in [
        "aplique", "aplicar", "massageie", "enxágue", "enxague",
        "use", "apply", "spread", "rinse", "wash", "lavar",
        "deixe", "aguarde", "espalhe", "distribua", "penteie",
        "seque", "secar",
    ])
    if not has_action_verb and len(text) > 50:
        return [FieldIssue(
            field="usage_instructions",
            code="usage_is_description",
            severity=IssueSeverity.WARNING,
            message="Usage instructions contain no action verbs — may be a description",
            details=usage[:100],
        )]
    return []


def _check_benefits_quality(benefits: list[str] | None) -> list[FieldIssue]:
    """Validate benefits_claims field."""
    if not benefits:
        return []
    issues: list[FieldIssue] = []
    # Very long items are likely descriptions, not claims
    long_items = [b for b in benefits if len(b.strip()) > 120]
    if long_items:
        issues.append(FieldIssue(
            field="benefits_claims",
            code="benefits_too_long",
            severity=IssueSeverity.WARNING,
            message=f"{len(long_items)} benefit(s) are very long — may be descriptions",
            details=long_items[0][:100],
        ))
    return issues


def _check_price(price: float | None, currency: str | None) -> list[FieldIssue]:
    """Validate price / currency consistency."""
    issues: list[FieldIssue] = []
    if price is not None:
        if price <= 0:
            issues.append(FieldIssue(
                field="price",
                code="price_invalid",
                severity=IssueSeverity.ERROR,
                message=f"Price is non-positive: {price}",
            ))
        elif price > 5000:
            issues.append(FieldIssue(
                field="price",
                code="price_outlier",
                severity=IssueSeverity.WARNING,
                message=f"Price seems unusually high: {price}",
            ))
        if not currency:
            issues.append(FieldIssue(
                field="currency",
                code="price_no_currency",
                severity=IssueSeverity.WARNING,
                message="Price is set but currency is missing",
            ))
    return issues


def _check_required_fields(
    product_name: str | None,
    image_url: str | None,
    product_type: str | None,
) -> list[FieldIssue]:
    """Check required/important fields are present."""
    issues: list[FieldIssue] = []
    if not product_name or not product_name.strip():
        issues.append(FieldIssue(
            field="product_name",
            code="name_missing",
            severity=IssueSeverity.ERROR,
            message="Product name is missing",
        ))
    if not image_url:
        issues.append(FieldIssue(
            field="image_url_main",
            code="image_missing",
            severity=IssueSeverity.WARNING,
            message="Product image is missing",
        ))
    if not product_type:
        issues.append(FieldIssue(
            field="product_type_normalized",
            code="type_missing",
            severity=IssueSeverity.INFO,
            message="Product type is not set",
        ))
    return issues


# ── Score Deductions ──

_DEDUCTIONS = {
    IssueSeverity.ERROR: 20,
    IssueSeverity.WARNING: 5,
    IssueSeverity.INFO: 0,
}


# ── Main Entry Point ──

def validate_product_fields(
    *,
    product_name: str | None = None,
    inci_ingredients: list[str] | None = None,
    description: str | None = None,
    usage_instructions: str | None = None,
    benefits_claims: list[str] | None = None,
    price: float | None = None,
    currency: str | None = None,
    image_url_main: str | None = None,
    product_type_normalized: str | None = None,
) -> ValidationReport:
    """Run all field cross-validation rules and return a report."""
    all_issues: list[FieldIssue] = []

    all_issues.extend(_check_required_fields(product_name, image_url_main, product_type_normalized))
    all_issues.extend(_check_inci_is_marketing(inci_ingredients))
    all_issues.extend(_check_inci_is_usage(inci_ingredients))
    all_issues.extend(_check_inci_has_sentences(inci_ingredients))
    all_issues.extend(_check_inci_marketing_complex(inci_ingredients))
    all_issues.extend(_check_description_quality(description))
    all_issues.extend(_check_usage_quality(usage_instructions))
    all_issues.extend(_check_benefits_quality(benefits_claims))
    all_issues.extend(_check_price(price, currency))

    score = 100
    for issue in all_issues:
        score -= _DEDUCTIONS.get(issue.severity, 0)
    score = max(0, score)

    return ValidationReport(issues=all_issues, score=score)
