# tests/api/test_api.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.storage.orm_models import Base, ProductORM, QuarantineDetailORM
from src.storage.repository import ProductRepository
from src.core.models import ProductExtraction, GenderTarget, QAResult, QAStatus


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def client(db_engine):
    def _override_session():
        with Session(db_engine) as session:
            yield session

    from src.api.routes.products import _get_session as prod_get_session
    from src.api.routes.brands import _get_session as brands_get_session
    from src.api.routes.quarantine import _get_session as quarantine_get_session

    app.dependency_overrides[prod_get_session] = _override_session
    app.dependency_overrides[brands_get_session] = _override_session
    app.dependency_overrides[quarantine_get_session] = _override_session

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def _seed_product(session, url="https://www.amend.com.br/p1", status="verified_inci"):
    p = ProductORM(
        brand_slug="amend",
        product_name="Shampoo Gold Black",
        product_url=url,
        image_url_main="https://img.com/x.jpg",
        verification_status=status,
        gender_target="unisex",
        confidence=0.9,
    )
    session.add(p)
    session.commit()
    return p


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestProductsEndpoint:
    def test_list_empty(self, client):
        resp = client.get("/api/products")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_list_verified(self, client, db_session):
        _seed_product(db_session, "https://amend.com.br/p1", "verified_inci")
        _seed_product(db_session, "https://amend.com.br/p2", "catalog_only")
        resp = client.get("/api/products?verified_only=true")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1
        assert body["total"] == 1

    def test_list_pagination(self, client, db_session):
        for i in range(5):
            _seed_product(db_session, f"https://amend.com.br/page{i}", "verified_inci")
        resp = client.get("/api/products?limit=2&offset=0")
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5
        assert body["limit"] == 2
        assert body["offset"] == 0
        # Second page
        resp2 = client.get("/api/products?limit=2&offset=2")
        body2 = resp2.json()
        assert len(body2["items"]) == 2
        assert body2["offset"] == 2

    def test_search(self, client, db_session):
        _seed_product(db_session, "https://amend.com.br/s1", "verified_inci")
        p2 = ProductORM(
            brand_slug="amend",
            product_name="Conditioner Shine",
            product_url="https://amend.com.br/s2",
            verification_status="verified_inci",
            gender_target="unisex",
            confidence=0.9,
        )
        db_session.add(p2)
        db_session.commit()
        # Search for "conditioner"
        resp = client.get("/api/products?search=conditioner")
        body = resp.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["product_name"] == "Conditioner Shine"
        assert body["total"] == 1

    def test_get_product_not_found(self, client):
        resp = client.get("/api/products/nonexistent")
        assert resp.status_code == 404

    def test_get_product_by_id(self, client, db_session):
        p = _seed_product(db_session)
        resp = client.get(f"/api/products/{p.id}")
        assert resp.status_code == 200
        assert resp.json()["product_name"] == "Shampoo Gold Black"

    def test_export_csv(self, client, db_session):
        _seed_product(db_session)
        resp = client.get("/api/products/export?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        lines = resp.text.strip().split("\n")
        assert len(lines) == 2  # header + 1 product
        assert "product_name" in lines[0]

    def test_export_json(self, client, db_session):
        _seed_product(db_session)
        resp = client.get("/api/products/export?format=json")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0]["product_name"] == "Shampoo Gold Black"


class TestBrandsEndpoint:
    def test_list_empty(self, client):
        resp = client.get("/api/brands")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_coverage_not_found(self, client):
        resp = client.get("/api/brands/nonexistent/coverage")
        assert resp.status_code == 404


def _seed_quarantined_product(session, url="https://www.amend.com.br/q1"):
    p = ProductORM(
        brand_slug="amend",
        product_name="Quarantined Shampoo",
        product_url=url,
        verification_status="quarantined",
        gender_target="unisex",
        confidence=0.3,
    )
    session.add(p)
    session.flush()
    q = QuarantineDetailORM(
        product_id=p.id,
        rejection_reason="Missing INCI ingredients",
        rejection_code="missing_inci",
        review_status="pending",
    )
    session.add(q)
    session.commit()
    return p, q


class TestQuarantineEndpoint:
    def test_list_empty(self, client):
        resp = client.get("/api/quarantine")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_pending(self, client, db_session):
        _seed_quarantined_product(db_session)
        resp = client.get("/api/quarantine?review_status=pending")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["rejection_reason"] == "Missing INCI ingredients"
        assert items[0]["rejection_code"] == "missing_inci"
        assert items[0]["product_name"] == "Quarantined Shampoo"

    def test_approve_not_found(self, client):
        resp = client.post("/api/quarantine/nonexistent/approve")
        assert resp.status_code == 404

    def test_approve_success(self, client, db_session):
        p, q = _seed_quarantined_product(db_session)
        resp = client.post(f"/api/quarantine/{q.id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        db_session.refresh(q)
        assert q.review_status == "approved"
        db_session.refresh(p)
        assert p.verification_status == "verified_inci"

    def test_reject_not_found(self, client):
        resp = client.post("/api/quarantine/nonexistent/reject")
        assert resp.status_code == 404

    def test_reject_success(self, client, db_session):
        p, q = _seed_quarantined_product(db_session)
        resp = client.post(f"/api/quarantine/{q.id}/reject?notes=Bad%20data")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        db_session.refresh(q)
        assert q.review_status == "rejected"
        assert q.reviewer_notes == "Bad data"
        # Product stays quarantined
        db_session.refresh(p)
        assert p.verification_status == "quarantined"

    def test_list_filters_by_status(self, client, db_session):
        _, q = _seed_quarantined_product(db_session, "https://amend.com.br/q2")
        # Reject it
        client.post(f"/api/quarantine/{q.id}/reject")
        # Pending list should be empty
        resp = client.get("/api/quarantine?review_status=pending")
        assert len(resp.json()) == 0
        # Rejected list should have it
        resp = client.get("/api/quarantine?review_status=rejected")
        assert len(resp.json()) == 1
