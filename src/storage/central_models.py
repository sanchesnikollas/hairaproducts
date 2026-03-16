# src/storage/central_models.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, String, Text, Float, Integer, DateTime,
)
from sqlalchemy.orm import DeclarativeBase


class CentralBase(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BrandDatabaseORM(CentralBase):
    __tablename__ = "brand_databases"

    id = Column(String(36), primary_key=True, default=_uuid)
    brand_slug = Column(String(255), nullable=False, unique=True)
    brand_name = Column(String(255), nullable=False)
    database_url = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    product_count = Column(Integer, nullable=False, default=0)
    inci_rate = Column(Float, nullable=False, default=0.0)
    platform = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
