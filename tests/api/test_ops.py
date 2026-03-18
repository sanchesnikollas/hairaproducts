from __future__ import annotations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
import bcrypt
from src.storage.orm_models import Base, ProductORM
from src.storage.ops_models import UserORM
from src.api.main import app
from src.api.auth import create_access_token


def _setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


def _seed_data(engine):
    pw = bcrypt.hashpw(b"test", bcrypt.gensalt()).decode()
    with Session(engine) as s:
        admin = UserORM(email="a@h.com", password_hash=pw, name="A", role="admin")
        s.add(admin)
        s.flush()
        for i in range(5):
            p = ProductORM(
                brand_slug="test",
                product_name=f"Product {i}",
                product_url=f"https://test.com/p{i}",
                verification_status="verified_inci" if i < 3 else "catalog_only",
                status_editorial="aprovado" if i < 3 else "pendente",
                status_publicacao="publicado" if i < 3 else "rascunho",
                confidence=80.0 if i < 3 else 20.0,
            )
            s.add(p)
        s.commit()
        return admin.user_id


class TestDashboard:
    def setup_method(self):
        self.engine = _setup()
        admin_id = _seed_data(self.engine)
        self.token = create_access_token(user_id=admin_id, role="admin")
        def override():
            with Session(self.engine) as s:
                yield s
        from src.api.dependencies import get_ops_session
        app.dependency_overrides[get_ops_session] = override
        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_dashboard_returns_kpis(self):
        r = self.client.get("/api/ops/dashboard", headers={"Authorization": f"Bearer {self.token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["kpis"]["total_products"] == 5
        assert data["kpis"]["published"] == 3
        assert data["kpis"]["pending_review"] == 2

    def test_dashboard_requires_auth(self):
        r = self.client.get("/api/ops/dashboard")
        assert r.status_code == 401
