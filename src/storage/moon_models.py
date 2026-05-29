"""Moon storage — feedback (👍/👎), conversations and messages.

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


class MoonConversationORM(Base):
    """A persisted Moon chat thread. Each conversation belongs to a user (or is
    anonymous, today) and groups a sequence of messages. `title` is auto-derived
    from the first user message; reviewers can rename it later."""
    __tablename__ = "moon_conversations"

    conversation_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=True, index=True)
    title = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    last_message_at = Column(DateTime, default=_utcnow, index=True)
    archived = Column(JSON, nullable=True)  # null = active; set to a timestamp/reason JSON when archived


class MoonMessageORM(Base):
    """One turn (user or assistant) in a Moon conversation. The assistant rows
    snapshot the moment: intent, kb_sources, analysis, alternatives — so we can
    audit past replies even when the engine evolves."""
    __tablename__ = "moon_messages"

    message_id = Column(String(36), primary_key=True, default=_uuid)
    conversation_id = Column(String(36), ForeignKey("moon_conversations.conversation_id"),
                             nullable=False, index=True)
    role = Column(String(12), nullable=False)             # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow, index=True)
    # Snapshot fields (assistant rows only)
    intent = Column(String(32), nullable=True)
    kb_sources = Column(JSON, nullable=True)
    analysis = Column(JSON, nullable=True)
    alternatives = Column(JSON, nullable=True)
