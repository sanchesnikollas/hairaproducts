# src/pipeline/report_generator.py
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class BrandReport:
    brand_slug: str
    discovered_total: int = 0
    hair_total: int = 0
    kits_total: int = 0
    non_hair_total: int = 0
    extracted_total: int = 0
    verified_inci_total: int = 0
    catalog_only_total: int = 0
    quarantined_total: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    @property
    def verified_inci_rate(self) -> float:
        if self.extracted_total == 0:
            return 0.0
        return self.verified_inci_total / self.extracted_total

    @property
    def failure_rate(self) -> float:
        if self.extracted_total == 0:
            return 0.0
        return self.quarantined_total / self.extracted_total

    def to_dict(self) -> dict:
        return {
            "brand_slug": self.brand_slug,
            "discovered_total": self.discovered_total,
            "hair_total": self.hair_total,
            "kits_total": self.kits_total,
            "non_hair_total": self.non_hair_total,
            "extracted_total": self.extracted_total,
            "verified_inci_total": self.verified_inci_total,
            "verified_inci_rate": round(self.verified_inci_rate, 4),
            "catalog_only_total": self.catalog_only_total,
            "quarantined_total": self.quarantined_total,
            "failure_rate": round(self.failure_rate, 4),
            "errors": self.errors,
            "started_at": str(self.started_at),
            "completed_at": str(self.completed_at) if self.completed_at else None,
        }

    def complete(self) -> None:
        self.completed_at = datetime.now(timezone.utc)


def generate_coverage_stats(report: BrandReport) -> dict:
    """Convert BrandReport to stats dict suitable for repository.upsert_brand_coverage."""
    return {
        "brand_slug": report.brand_slug,
        "discovered_total": report.discovered_total,
        "hair_total": report.hair_total,
        "kits_total": report.kits_total,
        "non_hair_total": report.non_hair_total,
        "extracted_total": report.extracted_total,
        "verified_inci_total": report.verified_inci_total,
        "verified_inci_rate": round(report.verified_inci_rate, 4),
        "catalog_only_total": report.catalog_only_total,
        "quarantined_total": report.quarantined_total,
        "status": "done",
        "blueprint_version": 1,
        "coverage_report": report.to_dict(),
    }
