"""Moon feedback — reviewer 👍/👎 on Moon replies.

Turns the reviewers' testing into tuning data. The north-star metric (% of
Moon replies rated useful) is computed from this table. Snapshots the profile
and the rated message so analysis doesn't depend on later state changes.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey

from src.storage.orm_models import Base, _uuid, _utcnow


class MoonFeedbackORM(Base):
    __tablename__ = "moon_feedback"

    feedback_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=True, index=True)
    rating = Column(String(4), nullable=False)            # "up" | "down"
    message_content = Column(Text, nullable=False)        # the Moon reply being rated
    user_message = Column(Text, nullable=True)            # what the user had asked
    profile_snapshot = Column(JSON, nullable=True)        # derived_hair_types + summary at the time
    product_id = Column(String(36), nullable=True)        # product in context, if any
    comment = Column(Text, nullable=True)                 # optional free-text from reviewer
    created_at = Column(DateTime, default=_utcnow, index=True)
