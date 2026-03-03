# src/extraction/evidence_tracker.py
from __future__ import annotations

from datetime import datetime, timezone

from src.core.models import Evidence, ExtractionMethod


def create_evidence(
    field_name: str,
    source_url: str,
    evidence_locator: str,
    raw_source_text: str,
    method: ExtractionMethod,
    source_section_label: str | None = None,
) -> Evidence:
    return Evidence(
        field_name=field_name,
        source_url=source_url,
        evidence_locator=evidence_locator,
        raw_source_text=raw_source_text[:2000],
        extraction_method=method,
        source_section_label=source_section_label,
        extracted_at=datetime.now(timezone.utc),
    )
