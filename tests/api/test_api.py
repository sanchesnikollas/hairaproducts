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
        assert resp.json() == []

    def test_list_verified(self, client, db_session):
        _seed_product(db_session, "https://amend.com.br/p1", "verified_inci")
        _seed_product(db_session, "https://amend.com.br/p2", "catalog_only")
        resp = client.get("/api/products?verified_only=true")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_product_not_found(self, client):
        resp = client.get("/api/products/nonexistent")
        assert resp.status_code == 404

    def test_get_product_by_id(self, client, db_session):
        p = _seed_product(db_session)
        resp = client.get(f"/api/products/{p.id}")
        assert resp.status_code == 200
        assert resp.json()["product_name"] == "Shampoo Gold Black"


class TestBrandsEndpoint:
    def test_list_empty(self, client):
        resp = client.get("/api/brands")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_coverage_not_found(self, client):
        resp = client.get("/api/brands/nonexistent/coverage")
        assert resp.status_code == 404


class TestQuarantineEndpoint:
    def test_list_empty(self, client):
        resp = client.get("/api/quarantine")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_approve_not_found(self, client):
        resp = client.post("/api/quarantine/nonexistent/approve")
        assert resp.status_code == 404
