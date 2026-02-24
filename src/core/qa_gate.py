# src/core/qa_gate.py
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from src.core.inci_validator import validate_inci_list
from src.core.models import ProductExtraction, QAResult, QAStatus
from src.core.taxonomy import HAIR_PRODUCT_TYPES


@dataclass
class QAConfig:
    min_inci_terms: int = 5
    min_confidence: float = 0.80


GARBAGE_NAMES: list[str] = [
    "404", "não encontrado", "não encontrada",
    "página não encontrada", "page not found",
    "produto indisponível", "product unavailable",
    "error", "erro",
]


def _check_domain(url: str, allowed_domains: list[str]) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return any(host == d or host.endswith(f".{d}") for d in allowed_domains)


def run_product_qa(
    product: ProductExtraction,
    allowed_domains: list[str],
    config: QAConfig | None = None,
) -> QAResult:
    if config is None:
        config = QAConfig()

    passed: list[str] = []
    failed: list[str] = []

    # Minimal checks (catalog_only)
    name_lower = product.product_name.strip().lower()
    if any(g in name_lower for g in GARBAGE_NAMES):
        failed.append("name_garbage")
    else:
        passed.append("name_valid")

    if _check_domain(product.product_url, allowed_domains):
        passed.append("domain_valid")
    else:
        failed.append("domain_unofficial")

    if product.image_url_main:
        passed.append("has_image")
    else:
        failed.append("no_image")

    if product.hair_relevance_reason:
        passed.append("hair_relevant")
    else:
        failed.append("no_hair_relevance")

    if failed:
        return QAResult(
            status=QAStatus.QUARANTINED,
            passed=False,
            checks_passed=passed,
            checks_failed=failed,
            rejection_reason="; ".join(failed),
        )

    # If no INCI, it's catalog_only
    if not product.inci_ingredients:
        return QAResult(
            status=QAStatus.CATALOG_ONLY,
            passed=True,
            checks_passed=passed,
            checks_failed=[],
        )

    # Full INCI checks
    inci_result = validate_inci_list(product.inci_ingredients)
    if not inci_result.valid:
        failed.append(f"inci_invalid:{inci_result.rejection_reason}")
        return QAResult(
            status=QAStatus.QUARANTINED,
            passed=False,
            checks_passed=passed,
            checks_failed=failed,
            rejection_reason=inci_result.rejection_reason,
        )
    passed.append("inci_valid")

    if product.confidence < config.min_confidence:
        failed.append("low_confidence")
        return QAResult(
            status=QAStatus.QUARANTINED,
            passed=False,
            checks_passed=passed,
            checks_failed=failed,
            rejection_reason=f"confidence {product.confidence} < {config.min_confidence}",
        )
    passed.append("confidence_ok")

    return QAResult(
        status=QAStatus.VERIFIED_INCI,
        passed=True,
        checks_passed=passed,
        checks_failed=[],
    )
