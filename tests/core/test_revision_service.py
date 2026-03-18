from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from src.storage.orm_models import Base
from src.storage.ops_models import UserORM, RevisionHistoryORM
from src.core.revision_service import create_revisions, get_entity_history


def make_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


class TestCreateRevisions:
    def test_creates_one_revision_per_changed_field(self):
        engine = make_engine()
        with Session(engine) as s:
            revs = create_revisions(
                session=s,
                entity_type="product",
                entity_id="prod-1",
                old_values={"product_name": "Old", "description": "Same"},
                new_values={"product_name": "New", "description": "Same"},
                changed_by="user-1",
                change_source="human",
            )
            assert len(revs) == 1
            assert revs[0].field_name == "product_name"
            assert revs[0].old_value == "Old"
            assert revs[0].new_value == "New"

    def test_no_revisions_when_nothing_changed(self):
        engine = make_engine()
        with Session(engine) as s:
            revs = create_revisions(
                session=s,
                entity_type="product",
                entity_id="prod-1",
                old_values={"product_name": "Same"},
                new_values={"product_name": "Same"},
                changed_by="user-1",
                change_source="human",
            )
            assert len(revs) == 0


class TestGetEntityHistory:
    def test_returns_revisions_ordered_by_date(self):
        engine = make_engine()
        with Session(engine) as s:
            create_revisions(s, "product", "p1", {"a": "1"}, {"a": "2"}, "u1", "human")
            create_revisions(s, "product", "p1", {"a": "2"}, {"a": "3"}, "u1", "human")
            history = get_entity_history(s, "product", "p1")
            assert len(history) == 2
            assert history[0].new_value == "2"
            assert history[1].new_value == "3"
