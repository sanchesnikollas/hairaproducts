# src/storage/orm_models.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, String, Text, Float, Integer, DateTime, ForeignKey, JSON, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProductORM(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=_uuid)
    brand_slug = Column(String(255), nullable=False, index=True)
    product_name = Column(String(500), nullable=False)
    product_url = Column(String(2000), nullable=False, unique=True)
    image_url_main = Column(String(2000), nullable=True)
    image_urls_gallery = Column(JSON, nullable=True)
    verification_status = Column(String(50), nullable=False, default="catalog_only")
    product_type_raw = Column(String(255), nullable=True)
    product_type_normalized = Column(String(100), nullable=True)
    product_category = Column(String(100), nullable=True, index=True)
    is_kit = Column(Boolean, nullable=False, default=False, index=True)
    gender_target = Column(String(20), nullable=False, default="unknown")
    hair_relevance_reason = Column(Text, nullable=True)
    inci_ingredients = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    usage_instructions = Column(Text, nullable=True)
    composition = Column(Text, nullable=True)
    care_usage = Column(Text, nullable=True)
    benefits_claims = Column(JSON, nullable=True)
    size_volume = Column(String(100), nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String(3), nullable=True)
    line_collection = Column(String(255), nullable=True)
    variants = Column(JSON, nullable=True)
    product_labels = Column(JSON, nullable=True, default=None)
    confidence = Column(Float, nullable=False, default=0.0)
    # --- Gold gate (AI-facing trust tier; see src/core/gold_gate.py) ---
    # The ONLY axis the Moon AI reads. Computed by evaluate_gold, never by a
    # bare status flip. raw|catalog|gold_candidate|gold|gold_rejected.
    gold_status = Column(String(20), nullable=False, default="raw", index=True)
    gold_blockers = Column(JSON, nullable=True)            # cached unmet criteria for the Ops checklist
    gold_evaluated_at = Column(DateTime, nullable=True)
    gold_reviewed_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    gold_review_notes = Column(Text, nullable=True)        # mandatory on gold_rejected
    field_provenance = Column(JSON, nullable=True)         # per-field {method, trust, source_url, at}
    # --- Hair classification fields (added 2026-04-28) ---
    ph = Column(Float, nullable=True, index=True)
    hair_type = Column(JSON, nullable=True)
    audience_age = Column(String(20), nullable=True, index=True)
    function_objective = Column(String(100), nullable=True, index=True)
    image_url_front = Column(String(2000), nullable=True)
    image_url_back = Column(String(2000), nullable=True)
    # EAN/barcode — strongest exact key for OCR /moon/identify (added 2026-06-18)
    ean = Column(String(50), nullable=True, index=True)
    # --- Ops Panel v1 columns ---
    status_operacional = Column(String(50), nullable=True)   # bruto|extraido|normalizado|parseado|validado
    status_editorial = Column(String(50), nullable=True)     # pendente|em_revisao|aprovado|corrigido|rejeitado
    status_publicacao = Column(String(50), nullable=True)    # rascunho|publicado|despublicado|arquivado
    assigned_to = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    confidence_factors = Column(JSON, nullable=True)
    interpretation_data = Column(JSON, nullable=True)
    application_data = Column(JSON, nullable=True)
    decision_data = Column(JSON, nullable=True)
    extraction_method = Column(String(50), nullable=True)
    extracted_at = Column(DateTime, nullable=True)
    # --- Soft delete (added 2026-06-02) ---
    # Hide-not-erase pattern: reviewer audits flag rows as not-a-product
    # (collection pages, blog posts, non_hair items). Rows stay queryable for
    # restore via /api/admin/products/restore. Default queries filter is_hidden.
    is_hidden = Column(Boolean, nullable=False, default=False, index=True)
    hidden_reason = Column(String(50), nullable=True)  # non_hair | page_not_product | bad_name | manual
    hidden_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    evidence = relationship("ProductEvidenceORM", back_populates="product", cascade="all, delete-orphan")
    quarantine_detail = relationship("QuarantineDetailORM", back_populates="product", uselist=False, cascade="all, delete-orphan")


class ProductEvidenceORM(Base):
    __tablename__ = "product_evidence"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    field_name = Column(String(100), nullable=False)
    source_url = Column(String(2000), nullable=False)
    evidence_locator = Column(Text, nullable=True)
    raw_source_text = Column(Text, nullable=True)
    extraction_method = Column(String(50), nullable=False)
    source_section_label = Column(String(255), nullable=True)
    extracted_at = Column(DateTime, nullable=False, default=_utcnow)

    product = relationship("ProductORM", back_populates="evidence")


class QuarantineDetailORM(Base):
    __tablename__ = "quarantine_details"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, unique=True)
    rejection_reason = Column(Text, nullable=False)
    rejection_code = Column(String(100), nullable=True)
    review_status = Column(String(20), nullable=False, default="pending")
    reviewer_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    product = relationship("ProductORM", back_populates="quarantine_detail")


class BrandCoverageORM(Base):
    __tablename__ = "brand_coverage"

    id = Column(String(36), primary_key=True, default=_uuid)
    brand_slug = Column(String(255), nullable=False, unique=True)
    discovered_total = Column(Integer, nullable=False, default=0)
    hair_total = Column(Integer, nullable=False, default=0)
    kits_total = Column(Integer, nullable=False, default=0)
    non_hair_total = Column(Integer, nullable=False, default=0)
    extracted_total = Column(Integer, nullable=False, default=0)
    verified_inci_total = Column(Integer, nullable=False, default=0)
    verified_inci_rate = Column(Float, nullable=False, default=0.0)
    catalog_only_total = Column(Integer, nullable=False, default=0)
    quarantined_total = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="active")
    last_run = Column(DateTime, nullable=True)
    blueprint_version = Column(Integer, nullable=False, default=1)
    coverage_report = Column(JSON, nullable=True)


class BrandRegistryORM(Base):
    """Catálogo editável de marcas. Seedado inicialmente do `config/brands.json`,
    mas a UI admin (`/ops/brands` → "+ Nova Marca") escreve direto aqui pra
    sobreviver a redeploys do container sem alterar o arquivo.

    `/api/brands` (list) mescla esta tabela com `brand_coverage` (live counts).
    """
    __tablename__ = "brand_registry"

    brand_slug = Column(String(255), primary_key=True)
    brand_name = Column(String(255), nullable=False)
    official_url_root = Column(String(2000), nullable=True)
    country = Column(String(80), nullable=True)        # Brasil | Internacional | Outros
    priority = Column(Integer, nullable=True)          # 1 (alta) | 2 | 3 | null
    status = Column(String(50), nullable=False, default="active")  # active | blocked | blocked_maintenance | out_of_scope
    platform = Column(String(50), nullable=True)       # VTEX | Shopify | WooCommerce | Custom | None
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class IngredientORM(Base):
    __tablename__ = "ingredients"
    id = Column(String(36), primary_key=True, default=_uuid)
    canonical_name = Column(Text, nullable=False, unique=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid()
        super().__init__(**kwargs)
    inci_name = Column(Text, nullable=True)
    cas_number = Column(String(50), nullable=True)
    category = Column(String(100), nullable=True)
    safety_rating = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    # Soft delete (2026-06-04): hide JS code, marketing sentences, product
    # names that contaminated the table during early extraction. See
    # scripts/cleanup_ingredients_phase1.py for the audit criteria.
    is_hidden = Column(Boolean, nullable=False, default=False, index=True)
    hidden_reason = Column(String(50), nullable=True)
    hidden_at = Column(DateTime, nullable=True)
    aliases = relationship("IngredientAliasORM", back_populates="ingredient", cascade="all, delete-orphan")
    product_ingredients = relationship("ProductIngredientORM", back_populates="ingredient")


class IngredientAliasORM(Base):
    __tablename__ = "ingredient_aliases"
    id = Column(String(36), primary_key=True, default=_uuid)
    ingredient_id = Column(String(36), ForeignKey("ingredients.id"), nullable=False)
    alias = Column(Text, nullable=False, unique=True)
    language = Column(String(10), nullable=False, default="en")
    ingredient = relationship("IngredientORM", back_populates="aliases")


class ProductIngredientORM(Base):
    __tablename__ = "product_ingredients"
    __table_args__ = (UniqueConstraint("product_id", "ingredient_id"),)
    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    ingredient_id = Column(String(36), ForeignKey("ingredients.id"), nullable=False, index=True)
    position = Column(Integer, nullable=True)
    raw_name = Column(Text, nullable=True)
    validation_status = Column(String(50), nullable=False, default="raw")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    product = relationship("ProductORM")
    ingredient = relationship("IngredientORM", back_populates="product_ingredients")


class ClaimORM(Base):
    __tablename__ = "claims"
    id = Column(String(36), primary_key=True, default=_uuid)
    canonical_name = Column(Text, nullable=False, unique=True)
    display_name = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    aliases = relationship("ClaimAliasORM", back_populates="claim", cascade="all, delete-orphan")


class ClaimAliasORM(Base):
    __tablename__ = "claim_aliases"
    id = Column(String(36), primary_key=True, default=_uuid)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False)
    alias = Column(Text, nullable=False, unique=True)
    language = Column(String(10), nullable=False, default="en")
    claim = relationship("ClaimORM", back_populates="aliases")


class ProductClaimORM(Base):
    __tablename__ = "product_claims"
    __table_args__ = (UniqueConstraint("product_id", "claim_id"),)
    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False, index=True)
    source = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)
    evidence_text = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    product = relationship("ProductORM")
    claim = relationship("ClaimORM")


class ProductImageORM(Base):
    __tablename__ = "product_images"
    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    url = Column(Text, nullable=False)
    image_type = Column(String(50), nullable=False, default="gallery")
    position = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    product = relationship("ProductORM")


class ProductCompositionORM(Base):
    __tablename__ = "product_compositions"
    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    section_label = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    source_selector = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    product = relationship("ProductORM")


class ExternalInciORM(Base):
    __tablename__ = "external_inci"

    id = Column(String(36), primary_key=True, default=_uuid)
    source = Column(String(50), nullable=False)
    source_url = Column(Text, nullable=False)
    brand_slug = Column(String(255), nullable=False, index=True)
    product_name = Column(Text, nullable=True)
    product_type = Column(String(100), nullable=True)
    inci_raw = Column(Text, nullable=True)
    inci_ingredients = Column(JSON, nullable=True)
    ean = Column(String(50), nullable=True)
    scraped_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("source", "source_url", name="uq_external_inci_source_url"),
    )


class EnrichmentQueueORM(Base):
    __tablename__ = "enrichment_queue"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), nullable=False, index=True)
    external_inci_id = Column(String(36), nullable=False)
    match_score = Column(Float, nullable=False)
    match_details = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    reviewed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class ValidationComparisonORM(Base):
    __tablename__ = "validation_comparisons"
    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    pass_1_value = Column(Text, nullable=True)
    pass_2_value = Column(Text, nullable=True)
    resolution = Column(String(50), nullable=False, default="pending")
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    product = relationship("ProductORM")
    review_queue_item = relationship("ReviewQueueORM", back_populates="comparison", uselist=False)


class ReviewQueueORM(Base):
    __tablename__ = "review_queue"
    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    comparison_id = Column(String(36), ForeignKey("validation_comparisons.id"), nullable=True)
    field_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)
    product = relationship("ProductORM")
    comparison = relationship("ValidationComparisonORM", back_populates="review_queue_item")


# Ensure ops_models (UserORM, etc.) are loaded so FK references resolve
import src.storage.ops_models as _ops_models  # noqa: F401, E402
