"""Knowledge base storage — the Doutoras' proprietary content.

Stored in DB (not git) because the repo is public. Loaded once at process
startup and held in memory (~45k tokens currently), injected as Moon's
cached system context. Sync local→prod via /api/admin/sync-knowledge-base.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Integer, DateTime

from src.storage.orm_models import Base, _utcnow


class KnowledgeChunkORM(Base):
    __tablename__ = "knowledge_chunks"

    # Original filename ("Dica do Dia.docx") — natural key.
    source = Column(String(255), primary_key=True)
    content = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
