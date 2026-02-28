# src/core/models.py
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class VerificationStatus(str, enum.Enum):
    CATALOG_ONLY = "catalog_only"
    VERIFIED_INCI = "verified_inci"
    QUARANTINED = "quarantined"


class GenderTarget(str, enum.Enum):
    MEN = "men"
    WOMEN = "women"
    UNISEX = "unisex"
    KIDS = "kids"
    UNKNOWN = "unknown"


class ExtractionMethod(str, enum.Enum):
    JSONLD = "jsonld"
    HTML_SELECTOR = "html_selector"
    JS_DOM = "js_dom"
    LLM_GROUNDED = "llm_grounded"
    MANUAL = "manual"


class QAStatus(str, enum.Enum):
    CATALOG_ONLY = "catalog_only"
    VERIFIED_INCI = "verified_inci"
    QUARANTINED = "quarantined"


class Brand(BaseModel):
    brand_name: str
    brand_slug: str
    official_url_root: str
    country: Optional[str] = None
    priority: Optional[int] = None
    catalog_entrypoints: list[str] = Field(default_factory=list)
    status: str = "active"
    notes: Optional[str] = None


class DiscoveredURL(BaseModel):
    url: str
    source_type: str
    hair_relevant: bool = False
    hair_relevance_reason: Optional[str] = None
    is_kit: bool = False


class Evidence(BaseModel):
    field_name: str
    source_url: str
    evidence_locator: str
    raw_source_text: str
    extraction_method: ExtractionMethod
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductExtraction(BaseModel):
    brand_slug: str
    product_name: str
    product_url: str
    image_url_main: Optional[str] = None
    image_urls_gallery: list[str] = Field(default_factory=list)
    gender_target: GenderTarget = GenderTarget.UNKNOWN
    hair_relevance_reason: str = ""
    product_type_raw: Optional[str] = None
    product_type_normalized: Optional[str] = None
    product_category: Optional[str] = None
    inci_ingredients: Optional[list[str]] = None
    description: Optional[str] = None
    usage_instructions: Optional[str] = None
    benefits_claims: Optional[list[str]] = None
    size_volume: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    line_collection: Optional[str] = None
    variants: Optional[list[dict]] = None
    confidence: float = 0.0
    extraction_method: Optional[str] = None
    evidence: list[Evidence] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QAResult(BaseModel):
    status: QAStatus
    passed: bool
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    rejection_reason: Optional[str] = None
