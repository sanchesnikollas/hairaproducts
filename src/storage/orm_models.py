# src/storage/orm_models.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Float, Integer, DateTime, ForeignKey, JSON, UniqueConstraint,
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
    gender_target = Column(String(20), nullable=False, default="unknown")
    hair_relevance_reason = Column(Text, nullable=True)
    inci_ingredients = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    usage_instructions = Column(Text, nullable=True)
    benefits_claims = Column(JSON, nullable=True)
    size_volume = Column(String(100), nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String(3), nullable=True)
    line_collection = Column(String(255), nullable=True)
    variants = Column(JSON, nullable=True)
    product_labels = Column(JSON, nullable=True, default=None)
    confidence = Column(Float, nullable=False, default=0.0)
    extraction_method = Column(String(50), nullable=True)
    extracted_at = Column(DateTime, nullable=True)
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
