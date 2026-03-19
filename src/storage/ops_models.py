from __future__ import annotations

from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey

from src.storage.orm_models import Base, _uuid, _utcnow


class UserORM(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False, default="reviewer")  # admin | reviewer
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_utcnow)
    last_login_at = Column(DateTime, nullable=True)


class RevisionHistoryORM(Base):
    __tablename__ = "revision_history"

    revision_id = Column(String(36), primary_key=True, default=_uuid)
    entity_type = Column(String(50), nullable=False)  # product | ingredient | claim
    entity_id = Column(String(36), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    change_source = Column(String(20), nullable=False, default="system")  # human | system | pipeline
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
