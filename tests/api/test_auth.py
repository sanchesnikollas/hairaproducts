from __future__ import annotations
import pytest
from src.api.auth import create_access_token, verify_token


class TestJWT:
    def test_create_and_verify_token(self):
        token = create_access_token(user_id="abc-123", role="admin")
        payload = verify_token(token)
        assert payload["sub"] == "abc-123"
        assert payload["role"] == "admin"

    def test_invalid_token_returns_none(self):
        payload = verify_token("garbage.token.value")
        assert payload is None

    def test_expired_token_returns_none(self):
        token = create_access_token(user_id="abc", role="admin", expires_minutes=-1)
        payload = verify_token(token)
        assert payload is None


import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from src.storage.orm_models import Base
from src.storage.ops_models import UserORM
from src.api.main import app


def _setup_test_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


def _seed_admin(engine):
    pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    with Session(engine) as s:
        user = UserORM(email="admin@haira.com", password_hash=pw, name="Admin", role="admin")
        s.add(user)
        s.commit()
        s.refresh(user)
        return user.user_id


class TestAuthEndpoints:
    def setup_method(self):
        self.engine = _setup_test_db()
        self.admin_id = _seed_admin(self.engine)

        def override_session():
            with Session(self.engine) as s:
                yield s

        from src.api.dependencies import get_ops_session
        app.dependency_overrides[get_ops_session] = override_session
        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_login_success(self):
        r = self.client.post("/api/auth/login", json={"email": "admin@haira.com", "password": "admin123"})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"

    def test_login_wrong_password(self):
        r = self.client.post("/api/auth/login", json={"email": "admin@haira.com", "password": "wrong"})
        assert r.status_code == 401

    def test_me_with_valid_token(self):
        login = self.client.post("/api/auth/login", json={"email": "admin@haira.com", "password": "admin123"})
        token = login.json()["token"]
        r = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == "admin@haira.com"

    def test_me_without_token(self):
        r = self.client.get("/api/auth/me")
        assert r.status_code == 401

    def test_create_user_as_admin(self):
        login = self.client.post("/api/auth/login", json={"email": "admin@haira.com", "password": "admin123"})
        token = login.json()["token"]
        r = self.client.post(
            "/api/auth/users",
            json={"email": "reviewer@haira.com", "password": "rev123", "name": "Reviewer", "role": "reviewer"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201
        assert r.json()["role"] == "reviewer"
