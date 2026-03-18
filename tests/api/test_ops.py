from __future__ import annotations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
import bcrypt
from src.storage.orm_models import Base, ProductORM, IngredientORM, ProductIngredientORM
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


class TestOpsProducts:
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

    def test_patch_product_creates_revision(self):
        with Session(self.engine) as s:
            p = s.query(ProductORM).first()
            pid = p.id
        r = self.client.patch(
            f"/api/ops/products/{pid}",
            json={"product_name": "Updated Name"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert r.status_code == 200
        r2 = self.client.get(
            f"/api/ops/products/{pid}/history",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert r2.status_code == 200
        revisions = r2.json()["revisions"]
        assert len(revisions) == 1
        assert revisions[0]["field_name"] == "product_name"
        assert revisions[0]["new_value"] == "Updated Name"

    def test_batch_update_status(self):
        with Session(self.engine) as s:
            ids = [p.id for p in s.query(ProductORM).limit(3).all()]
        r = self.client.patch(
            "/api/ops/products/batch",
            json={"product_ids": ids, "status_editorial": "em_revisao"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert r.status_code == 200
        assert r.json()["updated"] == 3


class TestReviewQueue:
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

    def test_get_review_queue_returns_pending_items(self):
        r = self.client.get("/api/ops/review-queue", headers={"Authorization": f"Bearer {self.token}"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 2

    def test_start_review_assigns_product(self):
        r = self.client.get("/api/ops/review-queue", headers={"Authorization": f"Bearer {self.token}"})
        pid = r.json()["items"][0]["id"]
        r2 = self.client.post(
            f"/api/ops/review-queue/{pid}/start",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert r2.status_code == 200
        with Session(self.engine) as s:
            p = s.query(ProductORM).filter(ProductORM.id == pid).first()
            assert p.status_editorial == "em_revisao"
            assert p.assigned_to is not None

    def test_resolve_review_approve(self):
        r = self.client.get("/api/ops/review-queue", headers={"Authorization": f"Bearer {self.token}"})
        pid = r.json()["items"][0]["id"]
        self.client.post(f"/api/ops/review-queue/{pid}/start", headers={"Authorization": f"Bearer {self.token}"})
        r3 = self.client.post(
            f"/api/ops/review-queue/{pid}/resolve",
            json={"decision": "approve"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert r3.status_code == 200
        with Session(self.engine) as s:
            p = s.query(ProductORM).filter(ProductORM.id == pid).first()
            assert p.status_editorial == "aprovado"
            assert p.status_publicacao == "publicado"


class TestOpsIngredients:
    def setup_method(self):
        self.engine = _setup()
        admin_id = _seed_data(self.engine)
        self.token = create_access_token(user_id=admin_id, role="admin")
        with Session(self.engine) as s:
            ing = IngredientORM(canonical_name="Water", inci_name="Aqua")
            s.add(ing)
            s.commit()
            self.ingredient_id = ing.id
        def override():
            with Session(self.engine) as s:
                yield s
        from src.api.dependencies import get_ops_session
        app.dependency_overrides[get_ops_session] = override
        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_patch_ingredient(self):
        r = self.client.patch(
            f"/api/ops/ingredients/{self.ingredient_id}",
            json={"category": "solvent"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert r.status_code == 200

    def test_get_gaps(self):
        r = self.client.get("/api/ops/ingredients/gaps", headers={"Authorization": f"Bearer {self.token}"})
        assert r.status_code == 200
        data = r.json()
        assert "uncategorized" in data

    def test_requires_admin(self):
        reviewer_token = create_access_token(user_id="rev-1", role="reviewer")
        r = self.client.patch(
            f"/api/ops/ingredients/{self.ingredient_id}",
            json={"category": "solvent"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert r.status_code == 403
