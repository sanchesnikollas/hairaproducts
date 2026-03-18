from __future__ import annotations
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from src.storage.orm_models import Base, ProductORM
from src.storage.ops_models import UserORM, RevisionHistoryORM


def make_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


class TestUserORM:
    def test_create_user(self):
        engine = make_engine()
        with Session(engine) as s:
            user = UserORM(
                email="admin@haira.com",
                password_hash="$2b$12$fakehash",
                name="Admin",
                role="admin",
            )
            s.add(user)
            s.commit()
            s.refresh(user)
            assert user.user_id is not None
            assert user.email == "admin@haira.com"
            assert user.role == "admin"
            assert user.is_active is True

    def test_email_unique_constraint(self):
        engine = make_engine()
        with Session(engine) as s:
            u1 = UserORM(email="dup@haira.com", password_hash="h", name="A", role="admin")
            u2 = UserORM(email="dup@haira.com", password_hash="h", name="B", role="reviewer")
            s.add_all([u1, u2])
            try:
                s.commit()
                assert False, "Should have raised IntegrityError"
            except Exception:
                s.rollback()


class TestRevisionHistoryORM:
    def test_create_revision(self):
        engine = make_engine()
        with Session(engine) as s:
            user = UserORM(email="r@haira.com", password_hash="h", name="R", role="reviewer")
            s.add(user)
            s.commit()
            s.refresh(user)

            rev = RevisionHistoryORM(
                entity_type="product",
                entity_id=str(uuid.uuid4()),
                field_name="product_name",
                old_value="Old Name",
                new_value="New Name",
                changed_by=user.user_id,
                change_source="human",
            )
            s.add(rev)
            s.commit()
            s.refresh(rev)
            assert rev.revision_id is not None
            assert rev.change_source == "human"


class TestProductORMOpsColumns:
    def test_new_status_columns_default_values(self):
        engine = make_engine()
        with Session(engine) as s:
            p = ProductORM(
                brand_slug="test",
                product_name="Test Product",
                product_url="https://test.com/product-1",
                verification_status="catalog_only",
            )
            s.add(p)
            s.commit()
            s.refresh(p)
            assert p.status_operacional is None
            assert p.status_editorial is None
            assert p.status_publicacao is None
            assert p.assigned_to is None
            assert p.confidence == 0.0

    def test_jsonb_columns_accept_dict(self):
        engine = make_engine()
        with Session(engine) as s:
            p = ProductORM(
                brand_slug="test",
                product_name="Test",
                product_url="https://test.com/product-2",
                verification_status="verified_inci",
                confidence_factors={"completude": 0.8, "parsing": 0.9, "validacao_humana": 0.0},
                interpretation_data={"formula_classification": "hidratacao"},
            )
            s.add(p)
            s.commit()
            s.refresh(p)
            assert p.confidence_factors["completude"] == 0.8
            assert p.interpretation_data["formula_classification"] == "hidratacao"
