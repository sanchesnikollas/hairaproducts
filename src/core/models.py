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


class AudienceAge(str, enum.Enum):
    UNDER_3 = "under_3"
    KIDS = "kids"
    TEEN = "teen"
    ADULT = "adult"


class FunctionObjective(str, enum.Enum):
    LIMPAR = "limpar"
    CONDICIONAR = "condicionar"
    HIDRATAR = "hidratar"
    NUTRIR = "nutrir"
    RECONSTRUIR = "reconstruir"
    DEFINIR = "definir"
    FINALIZAR = "finalizar"
    PROTEGER = "proteger"
    TRATAR = "tratar"
    MODELAR = "modelar"
    ESFOLIAR = "esfoliar"
    ALISAR = "alisar"
    ONDULAR = "ondular"
    COLORIR = "colorir"


class ExtractionMethod(str, enum.Enum):
    JSONLD = "jsonld"
    HTML_SELECTOR = "html_selector"
    JS_DOM = "js_dom"
    LLM_GROUNDED = "llm_grounded"
    MANUAL = "manual"
    EXTERNAL_ENRICHMENT = "external_enrichment"


class QAStatus(str, enum.Enum):
    CATALOG_ONLY = "catalog_only"
    VERIFIED_INCI = "verified_inci"
    QUARANTINED = "quarantined"


class GoldStatus(str, enum.Enum):
    """AI-facing trust tier — the ONLY axis the Moon AI reads.

    Separate from verification_status (extraction-time INCI signal). A product
    reaches GOLD only by passing every Gold criterion in gold_gate.evaluate_gold,
    never by a bare status flip.

    raw            -> not evaluated, OR disqualified (non-hair / quarantined / bad name)
    catalog        -> real hair product, but missing/untruthful on a required field
    gold_candidate -> all required fields present & truthful, but a soft trust signal
                      (low known-ingredient ratio, LLM-only INCI, mixed marketing) needs human eyes
    gold           -> every criterion passed; safe for the AI
    gold_rejected  -> a human reviewed a candidate and judged the data untrustworthy
    """
    RAW = "raw"
    CATALOG = "catalog"
    GOLD_CANDIDATE = "gold_candidate"
    GOLD = "gold"
    GOLD_REJECTED = "gold_rejected"


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
    source_section_label: Optional[str] = None
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
    composition: Optional[str] = None
    care_usage: Optional[str] = None
    benefits_claims: Optional[list[str]] = None
    size_volume: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    line_collection: Optional[str] = None
    variants: Optional[list[dict]] = None
    confidence: float = 0.0
    extraction_method: Optional[str] = None
    has_section_context: bool = False
    evidence: list[Evidence] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # --- Hair classification ---
    ph: Optional[float] = None
    hair_type: Optional[list[str]] = None
    audience_age: Optional[str] = None
    function_objective: Optional[str] = None
    image_url_front: Optional[str] = None
    image_url_back: Optional[str] = None


class QAResult(BaseModel):
    status: QAStatus
    passed: bool
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    rejection_reason: Optional[str] = None


class GoldBlocker(BaseModel):
    """One unmet Gold criterion. severity 'error' = hard (blocks Gold entirely);
    'warning' = soft (routes to gold_candidate for human review)."""
    code: str
    field: str
    message: str
    severity: str = "error"


class GoldEvaluation(BaseModel):
    gold_status: GoldStatus
    blockers: list[GoldBlocker] = Field(default_factory=list)
    field_report: dict = Field(default_factory=dict)

    @property
    def is_gold(self) -> bool:
        return self.gold_status == GoldStatus.GOLD

    def blockers_as_dicts(self) -> list[dict]:
        return [b.model_dump() for b in self.blockers]


class ValidationStatusLevel(str, enum.Enum):
    RAW = "raw"
    AUTO_VALIDATED = "auto_validated"
    DUAL_VALIDATED = "dual_validated"
    NEEDS_REVIEW = "needs_review"
    MANUALLY_VERIFIED = "manually_verified"


class Ingredient(BaseModel):
    id: str
    canonical_name: str
    inci_name: Optional[str] = None
    cas_number: Optional[str] = None
    category: Optional[str] = None
    safety_rating: Optional[str] = None
    aliases: list[str] = []


class Claim(BaseModel):
    id: str
    canonical_name: str
    display_name: Optional[str] = None
    category: Optional[str] = None
    aliases: list[str] = []


class ProductIngredientDetail(BaseModel):
    ingredient: Ingredient
    position: Optional[int] = None
    raw_name: Optional[str] = None
    validation_status: str = "raw"


class ValidationComparison(BaseModel):
    id: str
    product_id: str
    field_name: str
    pass_1_value: Optional[str] = None
    pass_2_value: Optional[str] = None
    resolution: str = "pending"


class ReviewQueueItem(BaseModel):
    id: str
    product_id: str
    field_name: str
    status: str = "pending"
    reviewer_notes: Optional[str] = None
    product_name: Optional[str] = None
    brand_slug: Optional[str] = None
    comparison: Optional[ValidationComparison] = None
