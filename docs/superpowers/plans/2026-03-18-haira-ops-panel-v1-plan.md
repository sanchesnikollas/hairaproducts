# HAIRA Ops Panel v1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the HAIRA frontend from a data browser into an operational panel for a 2-3 person team to validate, correct, and publish products with full traceability.

**Architecture:** Backend-first approach. New ORM models (User, RevisionHistory) + new columns on ProductORM + JWT auth + ops-specific API routes under `/api/ops/`. Frontend adds `/ops` route tree with dedicated layout and sidebar. Public routes remain untouched.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, bcrypt, PyJWT, React 19, TypeScript, Tailwind CSS 4, React Router 7

**Spec:** `docs/superpowers/specs/2026-03-18-haira-ops-panel-v1-design.md`

---

## File Structure

### Backend — New Files

| File | Responsibility |
|------|---------------|
| `src/storage/ops_models.py` | UserORM, RevisionHistoryORM |
| `src/core/ops_schemas.py` | Pydantic JSONB schemas: InterpretationData, ApplicationData, DecisionData |
| `src/core/confidence.py` | Confidence score calculator (3-factor formula) |
| `src/core/revision_service.py` | Create revision diffs, query history |
| `src/api/auth.py` | JWT utilities: create_token, verify_token, get_current_user dependency |
| `src/api/routes/auth.py` | POST /login, GET /me, POST+PATCH+GET /users |
| `src/api/routes/ops.py` | Dashboard, ops products (list+detail), review queue endpoints |
| `src/api/routes/ops_ingredients.py` | PATCH ingredient, alias CRUD, gaps detection |

### Backend — Modified Files

| File | Changes |
|------|---------|
| `src/storage/orm_models.py` | Add columns to ProductORM: status_operacional, status_editorial, status_publicacao, assigned_to, confidence_factors, interpretation_data, application_data, decision_data. Keep `confidence` attribute name (no rename — avoids breaking existing code). |
| `src/api/main.py` | Mount auth_router, ops_router, ops_ingredients_router |
| `src/storage/repository.py` | Add ops query methods (dashboard stats, review queue aggregation, ingredient gaps) |
| `src/api/dependencies.py` | Add `get_ops_session` dependency (single source, used by all ops routes) |

### Frontend — New Files

| File | Responsibility |
|------|---------------|
| `frontend/src/lib/auth.tsx` | AuthContext, useAuth hook, JWT storage, ProtectedRoute |
| `frontend/src/lib/ops-api.ts` | API client for /api/ops/* and /api/auth/* endpoints |
| `frontend/src/types/ops.ts` | Ops-specific TypeScript types |
| `frontend/src/components/ops/OpsLayout.tsx` | Sidebar layout for /ops/* routes |
| `frontend/src/pages/Login.tsx` | Login page |
| `frontend/src/pages/ops/OpsDashboard.tsx` | Dashboard with KPIs + attention blocks |
| `frontend/src/pages/ops/OpsProducts.tsx` | Product list with ops columns + batch actions |
| `frontend/src/pages/ops/OpsProductDetail.tsx` | 4-tab product detail with inline edit |
| `frontend/src/pages/ops/OpsReview.tsx` | Unified review queue with flow contínuo |
| `frontend/src/pages/ops/OpsIngredients.tsx` | Ingredient governance list + gaps |
| `frontend/src/pages/ops/OpsSettings.tsx` | User management (admin only) |
| `frontend/src/components/ops/RevisionTimeline.tsx` | Revision history timeline |

### Frontend — Modified Files

| File | Changes |
|------|---------|
| `frontend/src/App.tsx` | Add /login, /ops/* routes with OpsLayout |
| `frontend/src/components/Layout.tsx` | Add "Ops" button in header nav |

### Test Files

| File | Tests |
|------|-------|
| `tests/core/test_confidence.py` | Confidence score calculation |
| `tests/core/test_revision_service.py` | Revision diff creation and query |
| `tests/api/test_auth.py` | Login, JWT, role protection |
| `tests/api/test_ops.py` | Dashboard, ops products, review queue, ingredients |

---

## Chunk 1: Backend Schema & Auth Foundation

### Task 1: UserORM + RevisionHistoryORM

**Files:**
- Create: `src/storage/ops_models.py`
- Test: `tests/storage/test_ops_models.py`

- [ ] **Step 1: Write test for UserORM creation**

```python
# tests/storage/test_ops_models.py
from __future__ import annotations
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from src.storage.orm_models import Base
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/storage/test_ops_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.storage.ops_models'`

- [ ] **Step 3: Implement UserORM and RevisionHistoryORM**

```python
# src/storage/ops_models.py
from __future__ import annotations
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from src.storage.orm_models import Base, _uuid, _utcnow


class UserORM(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    role = Column(String, nullable=False, default="reviewer")  # admin | reviewer
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_utcnow)
    last_login_at = Column(DateTime, nullable=True)


class RevisionHistoryORM(Base):
    __tablename__ = "revision_history"

    revision_id = Column(String, primary_key=True, default=_uuid)
    entity_type = Column(String, nullable=False)  # product | ingredient | claim
    entity_id = Column(String, nullable=False, index=True)
    field_name = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(String, ForeignKey("users.user_id"), nullable=True)
    change_source = Column(String, nullable=False, default="system")  # human | system | pipeline
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
```

Note: Import `_uuid` and `_utcnow` from `orm_models.py` to reuse existing helpers. Check that these are exported (not prefixed with double underscore). If they are private, copy the definitions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/storage/test_ops_models.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage/ops_models.py tests/storage/test_ops_models.py
git commit -m "feat(ops): add UserORM and RevisionHistoryORM models"
```

---

### Task 2: Pydantic JSONB schemas

**Files:**
- Create: `src/core/ops_schemas.py`
- Test: `tests/core/test_ops_schemas.py`

- [ ] **Step 1: Write test for schema validation**

```python
# tests/core/test_ops_schemas.py
from __future__ import annotations
import pytest
from src.core.ops_schemas import InterpretationData, ApplicationData, DecisionData


class TestInterpretationData:
    def test_valid_data(self):
        d = InterpretationData(
            formula_classification="hidratacao",
            key_actives=["pantenol", "glicerina"],
            silicone_presence=False,
        )
        assert d.formula_classification == "hidratacao"

    def test_minimal_data(self):
        d = InterpretationData()
        assert d.formula_classification is None
        assert d.key_actives == []


class TestDecisionData:
    def test_ready_for_publication(self):
        d = DecisionData(
            summary="Shampoo suave para uso diario",
            ready_for_publication=True,
            requires_human_review=False,
        )
        assert d.ready_for_publication is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_ops_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement schemas**

```python
# src/core/ops_schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field


class InterpretationData(BaseModel):
    formula_classification: str | None = None
    key_actives: list[str] = Field(default_factory=list)
    formula_base: str | None = None
    silicone_presence: bool | None = None
    sulfate_presence: bool | None = None
    protein_presence: bool | None = None
    hydration_nutrition_balance: str | None = None
    treatment_intensity: str | None = None  # leve | medio | intenso


class ApplicationData(BaseModel):
    when_to_use: str | None = None
    when_to_avoid: str | None = None
    ideal_frequency: str | None = None
    ideal_hair_types: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)


class DecisionData(BaseModel):
    summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    ready_for_publication: bool = False
    requires_human_review: bool = True
    review_reason: str | None = None
    confidence_score: float | None = None  # Moon's assessment (Phase 2), distinct from ProductORM.confidence
    uncertainty_flags: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_ops_schemas.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/ops_schemas.py tests/core/test_ops_schemas.py
git commit -m "feat(ops): add Pydantic schemas for JSONB product layers"
```

---

### Task 3: Add ops columns to ProductORM

**Files:**
- Modify: `src/storage/orm_models.py`
- Test: `tests/storage/test_ops_models.py`

- [ ] **Step 1: Write test for new ProductORM columns**

Add to `tests/storage/test_ops_models.py`:

```python
from src.storage.orm_models import ProductORM


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/storage/test_ops_models.py::TestProductORMOpsColumns -v`
Expected: FAIL — `AttributeError` or similar (columns don't exist yet)

- [ ] **Step 3: Add columns to ProductORM**

In `src/storage/orm_models.py`, add these columns to the `ProductORM` class after the existing `confidence` column:

```python
    # --- Ops Panel v1 columns ---
    status_operacional = Column(String, nullable=True)   # bruto|extraido|normalizado|parseado|validado
    status_editorial = Column(String, nullable=True)     # pendente|em_revisao|aprovado|corrigido|rejeitado
    status_publicacao = Column(String, nullable=True)    # rascunho|publicado|despublicado|arquivado
    assigned_to = Column(String, ForeignKey("users.user_id"), nullable=True)
    confidence_factors = Column(JSON, nullable=True)
    interpretation_data = Column(JSON, nullable=True)
    application_data = Column(JSON, nullable=True)
    decision_data = Column(JSON, nullable=True)
```

**Do NOT rename the `confidence` attribute.** The existing codebase references `ProductORM.confidence` in many files (repository.py, qa_gate.py, products.py, cli/main.py, normalized_writer.py). Keep it as-is. The spec's `confidence_score` concept maps to this existing column — no rename needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/storage/test_ops_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite to check nothing breaks**

Run: `pytest tests/ -x -q`
Expected: All existing tests still pass. The `confidence` attribute is unchanged, so no existing references should break.

- [ ] **Step 6: Commit**

```bash
git add src/storage/orm_models.py tests/storage/test_ops_models.py
git commit -m "feat(ops): add status, assignment, and layer columns to ProductORM"
```

---

### Task 4: Ops session dependency

**Files:**
- Modify: `src/api/dependencies.py`

- [ ] **Step 1: Add `get_ops_session` to dependencies.py**

Add to `src/api/dependencies.py`:

```python
from src.storage.ops_models import UserORM  # noqa: ensure tables are created

def get_ops_session():
    """Session for ops tables (users, revision_history). Uses primary DB (not brand-specific).
    In multi-DB mode: uses central DB. In single-DB mode: uses the default engine."""
    if is_multi_db():
        engine = _router._central_engine
    else:
        from src.storage.database import get_engine
        engine = get_engine()
    with Session(engine) as session:
        yield session
```

This is the **single source of truth** for ops session dependency. All ops route files import this function. Tests override it via `app.dependency_overrides[get_ops_session] = override`.

- [ ] **Step 2: Commit**

```bash
git add src/api/dependencies.py
git commit -m "feat(ops): add get_ops_session dependency for auth and ops routes"
```

---

### Task 5: JWT auth utilities

**Files:**
- Create: `src/api/auth.py`
- Test: `tests/api/test_auth.py`

- [ ] **Step 1: Write tests for JWT creation and verification**

```python
# tests/api/test_auth.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_auth.py::TestJWT -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement JWT utilities**

```python
# src/api/auth.py
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from fastapi import Depends, HTTPException, Request

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "haira-ops-dev-secret-change-in-prod")
ALGORITHM = "HS256"
DEFAULT_EXPIRE_MINUTES = 1440  # 24h


def create_access_token(user_id: str, role: str, expires_minutes: int = DEFAULT_EXPIRE_MINUTES) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
        return None


def get_current_user(request: Request) -> dict[str, Any]:
    """FastAPI dependency: extracts and validates JWT from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = auth_header[7:]
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency: requires admin role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

- [ ] **Step 4: Install PyJWT if not present**

Run: `pip install PyJWT bcrypt`

Add to `pyproject.toml` dependencies if not already there.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_auth.py::TestJWT -v`
Expected: 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/auth.py tests/api/test_auth.py
git commit -m "feat(ops): add JWT auth utilities"
```

---

### Task 4: Auth API endpoints (login, me, user management)

**Files:**
- Create: `src/api/routes/auth.py`
- Modify: `src/api/main.py`
- Test: `tests/api/test_auth.py`

- [ ] **Step 1: Write tests for login and me endpoints**

Add to `tests/api/test_auth.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_auth.py::TestAuthEndpoints -v`
Expected: FAIL

- [ ] **Step 3: Implement auth routes**

```python
# src/api/routes/auth.py
from __future__ import annotations
from datetime import datetime, timezone
import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.api.auth import create_access_token, get_current_user, require_admin
from src.api.dependencies import get_ops_session
from src.storage.ops_models import UserORM

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str = "reviewer"


class UpdateUserRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None


@router.post("/login")
def login(body: LoginRequest, session: Session = Depends(get_ops_session)):
    user = session.query(UserORM).filter(UserORM.email == body.email, UserORM.is_active.is_(True)).first()
    if not user or not bcrypt.checkpw(body.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user.last_login_at = datetime.now(timezone.utc)
    session.commit()
    token = create_access_token(user_id=user.user_id, role=user.role)
    return {
        "token": token,
        "user": {"id": user.user_id, "name": user.name, "email": user.email, "role": user.role},
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user), session: Session = Depends(get_ops_session)):
    db_user = session.query(UserORM).filter(UserORM.user_id == user["sub"]).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": db_user.user_id, "name": db_user.name, "email": db_user.email, "role": db_user.role}


@router.post("/users", status_code=201)
def create_user(body: CreateUserRequest, admin: dict = Depends(require_admin), session: Session = Depends(get_ops_session)):
    existing = session.query(UserORM).filter(UserORM.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = UserORM(email=body.email, password_hash=pw_hash, name=body.name, role=body.role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"id": user.user_id, "name": user.name, "email": user.email, "role": user.role}


@router.get("/users")
def list_users(admin: dict = Depends(require_admin), session: Session = Depends(get_ops_session)):
    users = session.query(UserORM).order_by(UserORM.created_at).all()
    return [
        {"id": u.user_id, "name": u.name, "email": u.email, "role": u.role, "is_active": u.is_active}
        for u in users
    ]


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UpdateUserRequest, admin: dict = Depends(require_admin), session: Session = Depends(get_ops_session)):
    user = session.query(UserORM).filter(UserORM.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    session.commit()
    return {"id": user.user_id, "name": user.name, "email": user.email, "role": user.role, "is_active": user.is_active}
```

- [ ] **Step 4: Mount auth router in main.py**

In `src/api/main.py`, add:

```python
from src.api.routes.auth import router as auth_router

# In the router mounting section:
app.include_router(auth_router, prefix="/api")
```

The session dependency is already configured in Task 4 (`get_ops_session` in `dependencies.py`). It handles both single-DB and multi-DB mode.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_auth.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/auth.py src/api/main.py tests/api/test_auth.py
git commit -m "feat(ops): add auth endpoints - login, me, user CRUD"
```

---

### Task 5: Alembic migration for ops columns

**Files:**
- Create: new migration file via alembic

- [ ] **Step 1: Generate migration**

Run: `alembic revision --autogenerate -m "add ops panel columns and tables"`

This should detect:
- New table: `users`
- New table: `revision_history`
- New columns on `products`: status_operacional, status_editorial, status_publicacao, assigned_to, confidence_factors, interpretation_data, application_data, decision_data

- [ ] **Step 2: Review the generated migration**

Verify the migration does NOT drop the `confidence` column (it was renamed in Python but DB column stays `confidence`).

- [ ] **Step 3: Add data migration for status columns**

Add to the `upgrade()` function, after the schema changes:

```python
    # Backfill status columns from verification_status
    op.execute("""
        UPDATE products SET
            status_operacional = CASE
                WHEN verification_status = 'verified_inci' THEN 'validado'
                WHEN verification_status = 'catalog_only' THEN 'extraido'
                WHEN verification_status = 'quarantined' THEN 'extraido'
                ELSE 'bruto'
            END,
            status_editorial = CASE
                WHEN verification_status = 'verified_inci' THEN 'aprovado'
                WHEN verification_status = 'catalog_only' THEN 'pendente'
                WHEN verification_status = 'quarantined' THEN 'pendente'
                ELSE 'pendente'
            END,
            status_publicacao = CASE
                WHEN verification_status = 'verified_inci' THEN 'publicado'
                ELSE 'rascunho'
            END
        WHERE status_operacional IS NULL
    """)
```

- [ ] **Step 4: Test migration locally**

Run: `alembic upgrade head`
Expected: Migration applies without errors. Verify with: `sqlite3 haira.db ".schema products"` — new columns should appear.

- [ ] **Step 5: Commit**

```bash
git add src/storage/migrations/versions/
git commit -m "feat(ops): migration for ops columns, users, and revision_history tables"
```

---

## Chunk 2: Backend Services (Confidence + Revision)

### Task 6: Confidence score calculator

**Files:**
- Create: `src/core/confidence.py`
- Test: `tests/core/test_confidence.py`

- [ ] **Step 1: Write tests for confidence calculation**

```python
# tests/core/test_confidence.py
from __future__ import annotations
import pytest
from src.core.confidence import calculate_confidence


class TestConfidenceScore:
    def test_fully_complete_verified_product(self):
        score, factors = calculate_confidence(
            fields={"product_name": "X", "product_category": "hair_care", "brand_slug": "test",
                    "description": "desc", "inci_ingredients": "Water, Glycerin", "image_url_main": "http://img.jpg"},
            validated_ingredient_count=10,
            total_ingredient_count=10,
            status_editorial="aprovado",
        )
        assert score == 100.0
        assert factors["completude"] == 1.0
        assert factors["parsing"] == 1.0
        assert factors["validacao_humana"] == 1.0

    def test_empty_product(self):
        score, factors = calculate_confidence(
            fields={"product_name": None, "product_category": None, "brand_slug": None,
                    "description": None, "inci_ingredients": None, "image_url_main": None},
            validated_ingredient_count=0,
            total_ingredient_count=0,
            status_editorial="pendente",
        )
        assert score == 0.0

    def test_partial_product(self):
        score, factors = calculate_confidence(
            fields={"product_name": "Shampoo", "product_category": "hair_care", "brand_slug": "test",
                    "description": None, "inci_ingredients": "Water", "image_url_main": None},
            validated_ingredient_count=5,
            total_ingredient_count=10,
            status_editorial="em_revisao",
        )
        # completude: 4/6 = 0.667, parsing: 5/10 = 0.5, validacao: 0.5
        assert 40 < score < 60
        assert factors["completude"] == pytest.approx(4 / 6, rel=0.01)
        assert factors["parsing"] == 0.5
        assert factors["validacao_humana"] == 0.5

    def test_no_inci_gives_zero_parsing(self):
        score, factors = calculate_confidence(
            fields={"product_name": "X", "product_category": "Y", "brand_slug": "Z",
                    "description": "D", "inci_ingredients": None, "image_url_main": "I"},
            validated_ingredient_count=0,
            total_ingredient_count=0,
            status_editorial="aprovado",
        )
        assert factors["parsing"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_confidence.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement confidence calculator**

```python
# src/core/confidence.py
from __future__ import annotations

CRITICAL_FIELDS = ["product_name", "product_category", "brand_slug", "description", "inci_ingredients", "image_url_main"]
WEIGHT_COMPLETUDE = 0.40
WEIGHT_PARSING = 0.35
WEIGHT_VALIDACAO = 0.25

EDITORIAL_SCORES = {
    "pendente": 0.0,
    "em_revisao": 0.5,
    "aprovado": 1.0,
    "corrigido": 1.0,
    "rejeitado": 0.0,
}


def calculate_confidence(
    fields: dict[str, object],
    validated_ingredient_count: int,
    total_ingredient_count: int,
    status_editorial: str | None,
) -> tuple[float, dict[str, float]]:
    """Calculate confidence score (0-100) and return (score, factors)."""
    filled = sum(1 for f in CRITICAL_FIELDS if fields.get(f))
    completude = filled / len(CRITICAL_FIELDS)

    if not fields.get("inci_ingredients") or total_ingredient_count == 0:
        parsing = 0.0
    else:
        parsing = validated_ingredient_count / total_ingredient_count

    validacao = EDITORIAL_SCORES.get(status_editorial or "pendente", 0.0)

    score = (completude * WEIGHT_COMPLETUDE + parsing * WEIGHT_PARSING + validacao * WEIGHT_VALIDACAO) * 100
    factors = {"completude": completude, "parsing": parsing, "validacao_humana": validacao}
    return round(score, 2), factors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_confidence.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/confidence.py tests/core/test_confidence.py
git commit -m "feat(ops): add confidence score calculator"
```

---

### Task 7: Revision history service

**Files:**
- Create: `src/core/revision_service.py`
- Test: `tests/core/test_revision_service.py`

- [ ] **Step 1: Write tests for creating revisions from a diff**

```python
# tests/core/test_revision_service.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_revision_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement revision service**

```python
# src/core/revision_service.py
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from src.storage.ops_models import RevisionHistoryORM


def _serialize(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def create_revisions(
    session: Session,
    entity_type: str,
    entity_id: str,
    old_values: dict[str, object],
    new_values: dict[str, object],
    changed_by: str | None,
    change_source: str,
    change_reason: str | None = None,
) -> list[RevisionHistoryORM]:
    """Compare old and new values, create RevisionHistory for each changed field."""
    revisions = []
    for field in new_values:
        old_val = old_values.get(field)
        new_val = new_values[field]
        if _serialize(old_val) == _serialize(new_val):
            continue
        rev = RevisionHistoryORM(
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field,
            old_value=_serialize(old_val),
            new_value=_serialize(new_val),
            changed_by=changed_by,
            change_source=change_source,
            change_reason=change_reason,
        )
        session.add(rev)
        revisions.append(rev)
    if revisions:
        session.flush()
    return revisions


def get_entity_history(
    session: Session,
    entity_type: str,
    entity_id: str,
    field_name: str | None = None,
    limit: int = 100,
) -> list[RevisionHistoryORM]:
    """Return revision history for an entity, ordered by created_at."""
    q = session.query(RevisionHistoryORM).filter(
        RevisionHistoryORM.entity_type == entity_type,
        RevisionHistoryORM.entity_id == entity_id,
    )
    if field_name:
        q = q.filter(RevisionHistoryORM.field_name == field_name)
    return q.order_by(RevisionHistoryORM.created_at.asc()).limit(limit).all()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_revision_service.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/revision_service.py tests/core/test_revision_service.py
git commit -m "feat(ops): add revision history service for field-level diffs"
```

---

## Chunk 3: Backend Ops API Endpoints

### Task 8: Dashboard stats endpoint

**Files:**
- Create: `src/api/routes/ops.py`
- Modify: `src/api/main.py`
- Test: `tests/api/test_ops.py`

- [ ] **Step 1: Write test for dashboard endpoint**

```python
# tests/api/test_ops.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_ops.py::TestDashboard -v`
Expected: FAIL

- [ ] **Step 3: Implement ops router with dashboard endpoint**

```python
# src/api/routes/ops.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from src.api.auth import get_current_user, require_admin
from src.api.dependencies import get_ops_session
from src.storage.orm_models import ProductORM
from src.storage.ops_models import RevisionHistoryORM

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user), session: Session = Depends(get_ops_session)):
    from src.storage.orm_models import BrandCoverageORM

    total = session.query(func.count(ProductORM.id)).scalar() or 0
    pending = session.query(func.count(ProductORM.id)).filter(ProductORM.status_editorial == "pendente").scalar() or 0
    quarantined = session.query(func.count(ProductORM.id)).filter(
        ProductORM.verification_status == "quarantined"
    ).scalar() or 0
    published = session.query(func.count(ProductORM.id)).filter(ProductORM.status_publicacao == "publicado").scalar() or 0
    avg_conf = session.query(func.avg(ProductORM.confidence)).scalar() or 0.0

    # INCI coverage: weighted average from brand coverage stats
    coverages = session.query(BrandCoverageORM).all()
    if coverages:
        total_verified = sum(c.verified_inci_total or 0 for c in coverages)
        total_extracted = sum(c.extracted_total or 0 for c in coverages)
        inci_coverage = round(total_verified / total_extracted * 100, 1) if total_extracted > 0 else 0.0
    else:
        inci_coverage = 0.0

    low_confidence = (
        session.query(ProductORM)
        .filter(ProductORM.confidence < 50)
        .order_by(ProductORM.confidence.asc())
        .limit(20)
        .all()
    )

    recent_activity = (
        session.query(RevisionHistoryORM)
        .order_by(RevisionHistoryORM.created_at.desc())
        .limit(20)
        .all()
    )

    return {
        "kpis": {
            "total_products": total,
            "inci_coverage": inci_coverage,
            "pending_review": pending,
            "quarantined": quarantined,
            "published": published,
            "avg_confidence": round(float(avg_conf), 1),
        },
        "low_confidence": [
            {"id": p.id, "product_name": p.product_name, "brand_slug": p.brand_slug,
             "confidence": p.confidence, "status_editorial": p.status_editorial}
            for p in low_confidence
        ],
        "recent_activity": [
            {"revision_id": r.revision_id, "entity_type": r.entity_type, "entity_id": r.entity_id,
             "field_name": r.field_name, "changed_by": r.changed_by, "change_source": r.change_source,
             "created_at": str(r.created_at)}
            for r in recent_activity
        ],
    }
```

- [ ] **Step 4: Mount ops router in main.py**

In `src/api/main.py`:

```python
from src.api.routes.ops import router as ops_router
app.include_router(ops_router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_ops.py::TestDashboard -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/ops.py src/api/main.py tests/api/test_ops.py
git commit -m "feat(ops): add dashboard stats endpoint"
```

---

### Task 9: Ops product endpoints (PATCH with history, batch, history)

**Files:**
- Modify: `src/api/routes/ops.py`
- Test: `tests/api/test_ops.py`

- [ ] **Step 1: Write tests for ops product PATCH and history**

Add to `tests/api/test_ops.py`:

```python
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

    def _get_product_id(self):
        r = self.client.get("/api/ops/dashboard", headers={"Authorization": f"Bearer {self.token}"})
        low = r.json()["low_confidence"]
        return low[0]["id"] if low else None

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_ops.py::TestOpsProducts -v`
Expected: FAIL

- [ ] **Step 3: Add ops product endpoints to ops.py**

Add to `src/api/routes/ops.py`:

```python
from src.core.revision_service import create_revisions, get_entity_history
from src.core.confidence import calculate_confidence


class OpsProductUpdate(BaseModel):
    product_name: str | None = None
    description: str | None = None
    usage_instructions: str | None = None
    inci_ingredients: str | None = None
    product_category: str | None = None
    status_editorial: str | None = None
    status_publicacao: str | None = None
    status_operacional: str | None = None


class BatchStatusUpdate(BaseModel):
    product_ids: list[str]
    status_editorial: str | None = None
    status_publicacao: str | None = None


# --- Ops product list (separate from public /api/products) ---

@router.get("/products")
def ops_list_products(
    brand: str | None = None,
    status_editorial: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 30,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    q = session.query(ProductORM)
    if brand:
        q = q.filter(ProductORM.brand_slug == brand)
    if status_editorial:
        q = q.filter(ProductORM.status_editorial == status_editorial)
    if search:
        q = q.filter(ProductORM.product_name.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(ProductORM.confidence.asc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [
            {
                "id": p.id, "product_name": p.product_name, "brand_slug": p.brand_slug,
                "verification_status": p.verification_status,
                "status_operacional": p.status_operacional, "status_editorial": p.status_editorial,
                "status_publicacao": p.status_publicacao, "confidence": p.confidence,
                "assigned_to": p.assigned_to,
            }
            for p in items
        ],
        "total": total, "page": page, "per_page": per_page,
    }


# --- IMPORTANT: batch endpoint BEFORE parameterized {product_id} for correct FastAPI route matching ---

@router.patch("/products/batch")
def ops_batch_update(
    body: BatchStatusUpdate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    products = session.query(ProductORM).filter(ProductORM.id.in_(body.product_ids)).all()
    if len(products) != len(body.product_ids):
        raise HTTPException(status_code=400, detail="Some product IDs not found")

    updates = {}
    if body.status_editorial:
        updates["status_editorial"] = body.status_editorial
    if body.status_publicacao:
        updates["status_publicacao"] = body.status_publicacao

    for product in products:
        old_values = {f: getattr(product, f) for f in updates}
        for field, value in updates.items():
            setattr(product, field, value)
        create_revisions(session, "product", product.id, old_values, updates, user["sub"], "human")

    session.commit()
    return {"status": "ok", "updated": len(products)}


@router.get("/products/{product_id}/history")
def ops_product_history(
    product_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    revisions = get_entity_history(session, "product", product_id)
    return {
        "revisions": [
            {
                "revision_id": r.revision_id,
                "field_name": r.field_name,
                "old_value": r.old_value,
                "new_value": r.new_value,
                "changed_by": r.changed_by,
                "change_source": r.change_source,
                "change_reason": r.change_reason,
                "created_at": str(r.created_at),
            }
            for r in revisions
        ]
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_ops.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/ops.py tests/api/test_ops.py
git commit -m "feat(ops): add product PATCH with revision history and batch update"
```

---

### Task 10: Review queue endpoints

**Files:**
- Modify: `src/api/routes/ops.py`
- Test: `tests/api/test_ops.py`

- [ ] **Step 1: Write tests for review queue**

Add to `tests/api/test_ops.py`:

```python
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
        # Products with status_editorial=pendente or low confidence should appear
        assert len(items) >= 2  # the 2 catalog_only products

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_ops.py::TestReviewQueue -v`
Expected: FAIL

- [ ] **Step 3: Add review queue endpoints to ops.py**

Add to `src/api/routes/ops.py`:

```python
from sqlalchemy import or_


class ResolveRequest(BaseModel):
    decision: str  # approve | correct | reject
    notes: str | None = None
    corrections: dict | None = None


@router.get("/review-queue")
def get_review_queue(
    type: str | None = None,
    brand: str | None = None,
    page: int = 1,
    per_page: int = 20,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    q = session.query(ProductORM).filter(
        or_(
            ProductORM.status_editorial.in_(["pendente", "rejeitado"]),
            ProductORM.confidence < 50,
        )
    )
    if brand:
        q = q.filter(ProductORM.brand_slug == brand)

    total = q.count()
    items = q.order_by(ProductORM.confidence.asc()).offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [
            {
                "id": p.id,
                "product_name": p.product_name,
                "brand_slug": p.brand_slug,
                "status_editorial": p.status_editorial,
                "confidence": p.confidence,
                "verification_status": p.verification_status,
                "assigned_to": p.assigned_to,
                "created_at": str(p.created_at) if p.created_at else None,
            }
            for p in items
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/review-queue/{product_id}/start")
def start_review(
    product_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    product = session.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.assigned_to and product.assigned_to != user["sub"]:
        raise HTTPException(status_code=409, detail="Product already assigned to another reviewer")

    old_values = {"status_editorial": product.status_editorial, "assigned_to": product.assigned_to}
    product.status_editorial = "em_revisao"
    product.assigned_to = user["sub"]
    create_revisions(session, "product", product_id, old_values,
                     {"status_editorial": "em_revisao", "assigned_to": user["sub"]},
                     user["sub"], "human")
    session.commit()
    return {"status": "ok", "product_id": product_id}


@router.post("/review-queue/{product_id}/resolve")
def resolve_review(
    product_id: str,
    body: ResolveRequest,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    product = session.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Track status changes
    old_values = {"status_editorial": product.status_editorial, "status_publicacao": product.status_publicacao}

    if body.decision == "approve":
        product.status_editorial = "aprovado"
        product.status_publicacao = "publicado"
    elif body.decision == "correct":
        product.status_editorial = "corrigido"
        # Track field corrections in RevisionHistory too
        if body.corrections:
            correction_old = {}
            correction_new = {}
            for field, value in body.corrections.items():
                if hasattr(product, field):
                    correction_old[field] = getattr(product, field)
                    correction_new[field] = value
                    setattr(product, field, value)
            if correction_old:
                create_revisions(session, "product", product_id, correction_old, correction_new,
                                 user["sub"], "human", change_reason=body.notes)
    elif body.decision == "reject":
        product.status_editorial = "rejeitado"
    else:
        raise HTTPException(status_code=400, detail="Invalid decision")

    product.assigned_to = None
    new_values = {"status_editorial": product.status_editorial, "status_publicacao": product.status_publicacao}
    create_revisions(session, "product", product_id, old_values, new_values, user["sub"], "human",
                     change_reason=body.notes)
    session.commit()
    return {"status": "ok", "product_id": product_id, "decision": body.decision}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_ops.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/ops.py tests/api/test_ops.py
git commit -m "feat(ops): add unified review queue with start/resolve flow"
```

---

### Task 11: Ops ingredient endpoints

**Files:**
- Create: `src/api/routes/ops_ingredients.py`
- Modify: `src/api/main.py`
- Test: `tests/api/test_ops.py`

- [ ] **Step 1: Write tests for ingredient PATCH and gaps**

Add to `tests/api/test_ops.py`:

```python
from src.storage.orm_models import IngredientORM, ProductIngredientORM


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_ops.py::TestOpsIngredients -v`
Expected: FAIL

- [ ] **Step 3: Implement ops ingredient routes**

```python
# src/api/routes/ops_ingredients.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from src.api.auth import require_admin
from src.api.dependencies import get_ops_session
from src.storage.orm_models import IngredientORM, IngredientAliasORM, ProductIngredientORM
from src.core.revision_service import create_revisions

router = APIRouter(prefix="/ops/ingredients", tags=["ops-ingredients"])


class IngredientUpdate(BaseModel):
    canonical_name: str | None = None
    inci_name: str | None = None
    category: str | None = None
    safety_rating: str | None = None


class AliasCreate(BaseModel):
    alias: str
    language: str | None = None


@router.patch("/{ingredient_id}")
def update_ingredient(
    ingredient_id: str,
    body: IngredientUpdate,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    ing = session.query(IngredientORM).filter(IngredientORM.id == ingredient_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    updates = body.model_dump(exclude_none=True)
    old_values = {f: getattr(ing, f) for f in updates}
    for field, value in updates.items():
        setattr(ing, field, value)
    create_revisions(session, "ingredient", ingredient_id, old_values, updates, admin["sub"], "human")
    session.commit()
    return {"status": "ok", "ingredient_id": ingredient_id}


@router.post("/{ingredient_id}/aliases", status_code=201)
def add_alias(
    ingredient_id: str,
    body: AliasCreate,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    ing = session.query(IngredientORM).filter(IngredientORM.id == ingredient_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    alias = IngredientAliasORM(ingredient_id=ingredient_id, alias=body.alias, language=body.language)
    session.add(alias)
    session.commit()
    return {"status": "ok", "alias_id": alias.id}


@router.delete("/{ingredient_id}/aliases/{alias_id}")
def delete_alias(
    ingredient_id: str,
    alias_id: str,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    alias = session.query(IngredientAliasORM).filter(
        IngredientAliasORM.id == alias_id,
        IngredientAliasORM.ingredient_id == ingredient_id,
    ).first()
    if not alias:
        raise HTTPException(status_code=404, detail="Alias not found")
    session.delete(alias)
    session.commit()
    return {"status": "ok"}


@router.get("/gaps")
def get_gaps(
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_ops_session),
):
    uncategorized = (
        session.query(IngredientORM)
        .filter(IngredientORM.category.is_(None))
        .order_by(IngredientORM.canonical_name)
        .all()
    )

    # Orphan raw_names: ProductIngredient.raw_name that don't match any Ingredient canonical_name or alias
    # Note: ingredient_id is NOT nullable, so we can't check for null. Instead, find raw_names
    # whose linked ingredient has no category (proxy for "unresolved" ingredients).
    from sqlalchemy import and_
    orphans = (
        session.query(
            ProductIngredientORM.raw_name,
            func.count(ProductIngredientORM.id).label("product_count"),
        )
        .join(IngredientORM, ProductIngredientORM.ingredient_id == IngredientORM.id)
        .filter(IngredientORM.category.is_(None))
        .group_by(ProductIngredientORM.raw_name)
        .order_by(func.count(ProductIngredientORM.id).desc())
        .limit(100)
        .all()
    )

    return {
        "uncategorized": [
            {"id": i.id, "canonical_name": i.canonical_name, "inci_name": i.inci_name}
            for i in uncategorized
        ],
        "orphan_raw_names": [
            {"raw_name": o.raw_name, "product_count": o.product_count}
            for o in orphans
        ],
    }
```

- [ ] **Step 4: Mount ops_ingredients router in main.py**

In `src/api/main.py`:

```python
from src.api.routes.ops_ingredients import router as ops_ingredients_router
app.include_router(ops_ingredients_router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_ops.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/ops_ingredients.py src/api/main.py tests/api/test_ops.py
git commit -m "feat(ops): add ingredient governance endpoints - PATCH, aliases, gaps"
```

---

## Chunk 4: Frontend Foundation (Auth + Layout + Types)

### Task 12: Ops TypeScript types

**Files:**
- Create: `frontend/src/types/ops.ts`

- [ ] **Step 1: Create ops types file**

```typescript
// frontend/src/types/ops.ts

export interface OpsUser {
  id: string;
  name: string;
  email: string;
  role: "admin" | "reviewer";
}

export interface LoginResponse {
  token: string;
  user: OpsUser;
}

export interface DashboardKPIs {
  total_products: number;
  inci_coverage: number;
  pending_review: number;
  quarantined: number;
  published: number;
  avg_confidence: number;
}

export interface DashboardData {
  kpis: DashboardKPIs;
  low_confidence: LowConfidenceProduct[];
  recent_activity: RevisionEntry[];
}

export interface LowConfidenceProduct {
  id: string;
  product_name: string;
  brand_slug: string;
  confidence: number;
  status_editorial: string | null;
}

export interface RevisionEntry {
  revision_id: string;
  entity_type: string;
  entity_id: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_by: string | null;
  change_source: string;
  change_reason: string | null;
  created_at: string;
}

export interface ReviewQueueItem {
  id: string;
  product_name: string;
  brand_slug: string;
  status_editorial: string | null;
  confidence: number;
  verification_status: string;
  assigned_to: string | null;
  created_at: string | null;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface IngredientGaps {
  uncategorized: { id: string; canonical_name: string; inci_name: string | null }[];
  orphan_raw_names: { raw_name: string; product_count: number }[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/ops.ts
git commit -m "feat(ops): add TypeScript types for ops panel"
```

---

### Task 13: Ops API client

**Files:**
- Create: `frontend/src/lib/ops-api.ts`

- [ ] **Step 1: Create ops API client**

```typescript
// frontend/src/lib/ops-api.ts
import type {
  LoginResponse, OpsUser, DashboardData, ReviewQueueResponse,
  RevisionEntry, IngredientGaps,
} from "../types/ops";

const BASE = "/api";

function getToken(): string | null {
  return localStorage.getItem("haira_token");
}

async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    localStorage.removeItem("haira_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res;
}

// Auth
export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  return res.json();
}

export async function getMe(): Promise<OpsUser> {
  const res = await authFetch(`${BASE}/auth/me`);
  return res.json();
}

export async function createUser(data: { email: string; password: string; name: string; role: string }): Promise<OpsUser> {
  const res = await authFetch(`${BASE}/auth/users`, { method: "POST", body: JSON.stringify(data) });
  return res.json();
}

// Dashboard
export async function getDashboard(): Promise<DashboardData> {
  const res = await authFetch(`${BASE}/ops/dashboard`);
  return res.json();
}

// Products
export async function opsListProducts(params?: { brand?: string; status_editorial?: string; search?: string; page?: number }): Promise<any> {
  const qs = new URLSearchParams();
  if (params?.brand) qs.set("brand", params.brand);
  if (params?.status_editorial) qs.set("status_editorial", params.status_editorial);
  if (params?.search) qs.set("search", params.search);
  if (params?.page) qs.set("page", String(params.page));
  const res = await authFetch(`${BASE}/ops/products?${qs}`);
  return res.json();
}

export async function opsGetProduct(id: string): Promise<any> {
  const res = await authFetch(`${BASE}/ops/products/${id}`);
  return res.json();
}

export async function opsUpdateProduct(id: string, data: Record<string, unknown>): Promise<void> {
  await authFetch(`${BASE}/ops/products/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export async function getUsers(): Promise<OpsUser[]> {
  const res = await authFetch(`${BASE}/auth/users`);
  return res.json();
}

export async function opsBatchUpdate(productIds: string[], updates: Record<string, string>): Promise<void> {
  await authFetch(`${BASE}/ops/products/batch`, {
    method: "PATCH",
    body: JSON.stringify({ product_ids: productIds, ...updates }),
  });
}

export async function getProductHistory(id: string): Promise<{ revisions: RevisionEntry[] }> {
  const res = await authFetch(`${BASE}/ops/products/${id}/history`);
  return res.json();
}

// Review Queue
export async function getReviewQueue(params?: { type?: string; brand?: string; page?: number }): Promise<ReviewQueueResponse> {
  const qs = new URLSearchParams();
  if (params?.type) qs.set("type", params.type);
  if (params?.brand) qs.set("brand", params.brand);
  if (params?.page) qs.set("page", String(params.page));
  const res = await authFetch(`${BASE}/ops/review-queue?${qs}`);
  return res.json();
}

export async function startReview(productId: string): Promise<void> {
  await authFetch(`${BASE}/ops/review-queue/${productId}/start`, { method: "POST" });
}

export async function resolveReview(productId: string, decision: string, notes?: string): Promise<void> {
  await authFetch(`${BASE}/ops/review-queue/${productId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ decision, notes }),
  });
}

// Ingredients
export async function opsUpdateIngredient(id: string, data: Record<string, unknown>): Promise<void> {
  await authFetch(`${BASE}/ops/ingredients/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export async function getIngredientGaps(): Promise<IngredientGaps> {
  const res = await authFetch(`${BASE}/ops/ingredients/gaps`);
  return res.json();
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/ops-api.ts
git commit -m "feat(ops): add ops API client with auth header injection"
```

---

### Task 14: Auth context and protected route

**Files:**
- Create: `frontend/src/lib/auth.tsx`

- [ ] **Step 1: Create auth context**

```tsx
// frontend/src/lib/auth.tsx
import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { getMe, login as apiLogin } from "./ops-api";
import type { OpsUser } from "../types/ops";

interface AuthContextType {
  user: OpsUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<OpsUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("haira_token");
    if (!token) {
      setLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => localStorage.removeItem("haira_token"))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await apiLogin(email, password);
    localStorage.setItem("haira_token", res.token);
    setUser(res.user);
  };

  const logout = () => {
    localStorage.removeItem("haira_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAdmin: user?.role === "admin" }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/auth.tsx
git commit -m "feat(ops): add AuthProvider context with JWT persistence"
```

---

### Task 15: Login page

**Files:**
- Create: `frontend/src/pages/Login.tsx`

- [ ] **Step 1: Create login page**

```tsx
// frontend/src/pages/Login.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/ops");
    } catch {
      setError("Credenciais invalidas");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream">
      <div className="w-full max-w-sm rounded-xl border border-cream-dark bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-center text-xl font-semibold text-ink">HAIRA Ops</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-ink-muted">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-ink-muted">Senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink"
              required
            />
          </div>
          {error && <p className="text-sm text-coral">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-ink py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Login.tsx
git commit -m "feat(ops): add login page"
```

---

### Task 16: Ops layout with sidebar

**Files:**
- Create: `frontend/src/components/ops/OpsLayout.tsx`

- [ ] **Step 1: Create ops layout with sidebar navigation**

```tsx
// frontend/src/components/ops/OpsLayout.tsx
import { NavLink, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { LayoutDashboard, Package, ListChecks, FlaskConical, Settings, LogOut } from "lucide-react";

const NAV_ITEMS = [
  { to: "/ops", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/ops/products", icon: Package, label: "Produtos" },
  { to: "/ops/review", icon: ListChecks, label: "Revisao" },
  { to: "/ops/ingredients", icon: FlaskConical, label: "Ingredientes", admin: true },
  { to: "/ops/settings", icon: Settings, label: "Settings", admin: true },
];

export default function OpsLayout() {
  const { user, loading, logout, isAdmin } = useAuth();

  if (loading) return <div className="flex h-screen items-center justify-center text-ink-muted">Carregando...</div>;
  if (!user) return <Navigate to="/login" replace />;

  const visibleItems = NAV_ITEMS.filter((item) => !item.admin || isAdmin);

  return (
    <div className="flex h-screen bg-cream">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r border-cream-dark bg-white">
        <div className="border-b border-cream-dark px-4 py-4">
          <h2 className="text-sm font-semibold text-ink">HAIRA Ops</h2>
          <p className="text-xs text-ink-muted">{user.name} ({user.role})</p>
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {visibleItems.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive ? "bg-cream font-medium text-ink" : "text-ink-muted hover:bg-cream hover:text-ink"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-cream-dark p-2">
          <button
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-muted transition-colors hover:bg-cream hover:text-ink"
          >
            <LogOut size={16} />
            Sair
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ops/OpsLayout.tsx
git commit -m "feat(ops): add ops layout with sidebar navigation"
```

---

### Task 17: Wire routes in App.tsx and add Ops button to Layout

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: Add ops routes to App.tsx**

Import and add the following routes:

```tsx
import { AuthProvider } from "./lib/auth";
import Login from "./pages/Login";
import OpsLayout from "./components/ops/OpsLayout";
import OpsDashboard from "./pages/ops/OpsDashboard";
import OpsProducts from "./pages/ops/OpsProducts";
import OpsReview from "./pages/ops/OpsReview";
import OpsIngredients from "./pages/ops/OpsIngredients";
import OpsSettings from "./pages/ops/OpsSettings";
```

Wrap the entire `<RouterProvider>` (or `<BrowserRouter>`) with `<AuthProvider>`.

Add routes:

```tsx
<Route path="/login" element={<Login />} />
<Route path="/ops" element={<OpsLayout />}>
  <Route index element={<OpsDashboard />} />
  <Route path="products" element={<OpsProducts />} />
  <Route path="review" element={<OpsReview />} />
  <Route path="ingredients" element={<OpsIngredients />} />
  <Route path="settings" element={<OpsSettings />} />
</Route>
```

- [ ] **Step 2: Add "Ops" button to Layout.tsx header**

In the nav items section of `Layout.tsx`, add after the existing nav links:

```tsx
<NavLink
  to="/ops"
  className={({ isActive }) =>
    `text-sm font-medium transition-colors ${isActive ? "text-ink" : "text-ink-muted hover:text-ink"}`
  }
>
  Ops
</NavLink>
```

- [ ] **Step 3: Create placeholder pages for ops routes**

Create minimal placeholder pages so the app compiles. Each page should just render its name:

```tsx
// frontend/src/pages/ops/OpsDashboard.tsx
export default function OpsDashboard() {
  return <div><h1 className="text-xl font-semibold text-ink">Dashboard</h1></div>;
}
```

Repeat for `OpsProducts.tsx`, `OpsReview.tsx`, `OpsIngredients.tsx`, `OpsSettings.tsx`.

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/pages/ops/
git commit -m "feat(ops): wire ops routes, layout, and placeholder pages"
```

---

## Chunk 5: Frontend Ops Pages

### Task 18: Ops Dashboard page

**Files:**
- Modify: `frontend/src/pages/ops/OpsDashboard.tsx`

- [ ] **Step 1: Implement dashboard with KPIs and attention blocks**

```tsx
// frontend/src/pages/ops/OpsDashboard.tsx
import { useAPI } from "../../hooks/useAPI";
import { getDashboard } from "../../lib/ops-api";
import type { DashboardData } from "../../types/ops";
import { Link } from "react-router-dom";
import { Package, AlertTriangle, CheckCircle, Clock } from "lucide-react";

function KPICard({ label, value, icon: Icon }: { label: string; value: number | string; icon: typeof Package }) {
  return (
    <div className="rounded-xl border border-cream-dark bg-white p-4">
      <div className="flex items-center gap-2 text-ink-muted">
        <Icon size={14} />
        <span className="text-xs">{label}</span>
      </div>
      <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

export default function OpsDashboard() {
  const { data, loading, error } = useAPI<DashboardData>(() => getDashboard(), []);

  if (loading) return <p className="text-ink-muted">Carregando...</p>;
  if (error) return <p className="text-coral">{error}</p>;
  if (!data) return null;

  const { kpis, low_confidence, recent_activity } = data;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-ink">Dashboard Operacional</h1>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <KPICard label="Total produtos" value={kpis.total_products} icon={Package} />
        <KPICard label="INCI Coverage" value={`${kpis.inci_coverage}%`} icon={CheckCircle} />
        <KPICard label="Pendentes revisao" value={kpis.pending_review} icon={Clock} />
        <KPICard label="Em quarentena" value={kpis.quarantined} icon={AlertTriangle} />
        <KPICard label="Publicados" value={kpis.published} icon={CheckCircle} />
        <KPICard label="Confianca media" value={`${kpis.avg_confidence}%`} icon={Package} />
      </div>

      {/* Low confidence */}
      {low_confidence.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-medium text-ink-muted">Baixa confianca</h2>
          <div className="space-y-2">
            {low_confidence.slice(0, 10).map((p) => (
              <Link
                key={p.id}
                to={`/ops/products?highlight=${p.id}`}
                className="flex items-center justify-between rounded-lg border border-cream-dark bg-white px-4 py-2 text-sm transition-colors hover:bg-cream"
              >
                <span className="text-ink">{p.product_name}</span>
                <span className="text-xs text-ink-muted">{p.brand_slug} · {p.confidence}%</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Recent activity */}
      {recent_activity.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-medium text-ink-muted">Atividade recente</h2>
          <div className="space-y-2">
            {recent_activity.map((r) => (
              <div key={r.revision_id} className="flex items-center gap-3 rounded-lg border border-cream-dark bg-white px-4 py-2 text-sm">
                <span className="text-ink">{r.field_name}</span>
                <span className="text-ink-muted">·</span>
                <span className="text-ink-muted">{r.entity_type}</span>
                <span className="ml-auto text-xs text-ink-faint">{r.change_source}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ops/OpsDashboard.tsx
git commit -m "feat(ops): implement dashboard page with KPIs and attention blocks"
```

---

### Task 19: Ops Products page

**Files:**
- Modify: `frontend/src/pages/ops/OpsProducts.tsx`

- [ ] **Step 1: Implement products page with ops columns and batch actions**

```tsx
// frontend/src/pages/ops/OpsProducts.tsx
import { useState } from "react";
import { useAPI } from "../../hooks/useAPI";
import { opsListProducts, opsBatchUpdate } from "../../lib/ops-api";
import { useAuth } from "../../lib/auth";
import { Link } from "react-router-dom";

export default function OpsProducts() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const { isAdmin } = useAuth();

  const { data, loading, refetch } = useAPI(
    () => opsListProducts({ page, search: search || undefined }),
    [page, search],
  );

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleBatchAction = async (updates: Record<string, string>) => {
    if (selected.size === 0) return;
    await opsBatchUpdate(Array.from(selected), updates);
    setSelected(new Set());
    refetch();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ink">Produtos</h1>
        {selected.size > 0 && (
          <div className="flex gap-2">
            <button
              onClick={() => handleBatchAction({ status_editorial: "aprovado" })}
              className="rounded-lg bg-sage/10 px-3 py-1.5 text-xs font-medium text-sage"
            >
              Aprovar ({selected.size})
            </button>
            {isAdmin && (
              <button
                onClick={() => handleBatchAction({ status_publicacao: "publicado" })}
                className="rounded-lg bg-ink/10 px-3 py-1.5 text-xs font-medium text-ink"
              >
                Publicar ({selected.size})
              </button>
            )}
          </div>
        )}
      </div>

      <input
        type="text"
        placeholder="Buscar produtos..."
        value={search}
        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        className="w-full max-w-md rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm outline-none focus:border-ink"
      />

      {loading ? (
        <p className="text-ink-muted">Carregando...</p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-cream-dark bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-cream-dark text-left text-xs text-ink-muted">
                  <th className="p-3 w-8"></th>
                  <th className="p-3">Produto</th>
                  <th className="p-3">Marca</th>
                  <th className="p-3">Editorial</th>
                  <th className="p-3">Publicacao</th>
                  <th className="p-3">Confianca</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((p: any) => (
                  <tr key={p.id} className="border-b border-cream-dark/50 hover:bg-cream/50">
                    <td className="p-3">
                      <input
                        type="checkbox"
                        checked={selected.has(p.id)}
                        onChange={() => toggleSelect(p.id)}
                      />
                    </td>
                    <td className="p-3">
                      <Link to={`/ops/products/${p.id}`} className="text-ink hover:underline">{p.product_name}</Link>
                    </td>
                    <td className="p-3 text-ink-muted">{p.brand_slug}</td>
                    <td className="p-3">
                      <span className="rounded-full bg-cream px-2 py-0.5 text-xs">
                        {p.status_editorial || "—"}
                      </span>
                    </td>
                    <td className="p-3">
                      <span className="rounded-full bg-cream px-2 py-0.5 text-xs">
                        {p.status_publicacao || "—"}
                      </span>
                    </td>
                    <td className="p-3 text-ink-muted">{p.confidence ?? "—"}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm text-ink-muted">
            <span>{data?.total ?? 0} produtos</span>
            <div className="flex gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className="rounded px-2 py-1 hover:bg-cream disabled:opacity-50">Anterior</button>
              <span>Pagina {page}</span>
              <button onClick={() => setPage((p) => p + 1)} disabled={!data || data.items.length < 30}
                className="rounded px-2 py-1 hover:bg-cream disabled:opacity-50">Proxima</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ops/OpsProducts.tsx
git commit -m "feat(ops): implement products page with batch actions and ops columns"
```

---

### Task 20: OpsProductDetail page with 4 tabs and inline edit

**Files:**
- Create: `frontend/src/pages/ops/OpsProductDetail.tsx`

- [ ] **Step 1: Implement 4-tab product detail with inline editing and revision history**

```tsx
// frontend/src/pages/ops/OpsProductDetail.tsx
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";
import { opsGetProduct, opsUpdateProduct } from "../../lib/ops-api";
import { fetchProductIngredients } from "../../lib/api";
import { RevisionTimeline } from "../../components/ops/RevisionTimeline";
import { useAuth } from "../../lib/auth";

type Tab = "raw" | "interpretation" | "application" | "decision" | "history";

export default function OpsProductDetail() {
  const { id } = useParams<{ id: string }>();
  const { isAdmin } = useAuth();
  const [tab, setTab] = useState<Tab>("raw");
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [pendingChanges, setPendingChanges] = useState<Record<string, { old: string; new: string }>>({});
  const [saving, setSaving] = useState(false);

  const { data: product, loading, refetch } = useAPI(() => opsGetProduct(id!), [id]);
  const { data: ingredients } = useAPI(() => fetchProductIngredients(id!), [id]);

  if (loading || !product) return <p className="text-ink-muted">Carregando...</p>;

  const startEdit = (field: string, value: string) => {
    setEditing((prev) => ({ ...prev, [field]: value }));
  };

  const commitEdit = (field: string) => {
    const newVal = editing[field];
    const oldVal = product[field] || "";
    if (newVal !== oldVal) {
      setPendingChanges((prev) => ({ ...prev, [field]: { old: oldVal, new: newVal } }));
    }
    setEditing((prev) => { const next = { ...prev }; delete next[field]; return next; });
  };

  const handleSave = async () => {
    if (Object.keys(pendingChanges).length === 0) return;
    setSaving(true);
    const updates: Record<string, string> = {};
    for (const [field, { new: val }] of Object.entries(pendingChanges)) {
      updates[field] = val;
    }
    await opsUpdateProduct(id!, updates);
    setPendingChanges({});
    setSaving(false);
    refetch();
  };

  const handleStatusChange = async (field: string, value: string) => {
    await opsUpdateProduct(id!, { [field]: value });
    refetch();
  };

  const EditableField = ({ field, label }: { field: string; label: string }) => {
    const value = product[field] || "";
    const isEditing = field in editing;
    return (
      <div className="space-y-1">
        <label className="text-xs text-ink-muted">{label}</label>
        {isEditing ? (
          <input
            value={editing[field]}
            onChange={(e) => setEditing((prev) => ({ ...prev, [field]: e.target.value }))}
            onBlur={() => commitEdit(field)}
            autoFocus
            className="w-full rounded border border-ink/20 bg-cream px-2 py-1 text-sm outline-none"
          />
        ) : (
          <p onClick={() => startEdit(field, value)}
            className="cursor-pointer rounded px-2 py-1 text-sm text-ink hover:bg-cream">
            {value || <span className="text-ink-faint italic">vazio</span>}
          </p>
        )}
        {pendingChanges[field] && (
          <p className="text-xs text-amber">
            "{pendingChanges[field].old}" → "{pendingChanges[field].new}"
          </p>
        )}
      </div>
    );
  };

  const TABS: { key: Tab; label: string }[] = [
    { key: "raw", label: "Dados Brutos" },
    { key: "interpretation", label: "Interpretacao" },
    { key: "application", label: "Aplicacao" },
    { key: "decision", label: "Decisao" },
    { key: "history", label: "Historico" },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-ink">{product.product_name}</h1>
      <p className="text-sm text-ink-muted">{product.brand_slug} · {product.verification_status}</p>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-cream-dark">
        {TABS.map(({ key, label }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-3 py-2 text-sm ${tab === key ? "border-b-2 border-ink font-medium text-ink" : "text-ink-muted"}`}>
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="rounded-xl border border-cream-dark bg-white p-6">
        {tab === "raw" && (
          <div className="space-y-4">
            <EditableField field="product_name" label="Nome" />
            <EditableField field="description" label="Descricao" />
            <EditableField field="product_category" label="Categoria" />
            <EditableField field="usage_instructions" label="Modo de uso" />
            <div>
              <label className="text-xs text-ink-muted">INCI</label>
              <p className="text-sm text-ink whitespace-pre-wrap">{product.inci_ingredients || "—"}</p>
            </div>
            {ingredients && ingredients.length > 0 && (
              <div>
                <label className="text-xs text-ink-muted">Ingredientes parseados ({ingredients.length})</label>
                <div className="mt-1 flex flex-wrap gap-1">
                  {ingredients.map((i: any) => (
                    <span key={i.position} className="rounded bg-cream px-1.5 py-0.5 text-xs text-ink-muted">
                      {i.canonical_name || i.raw_name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === "interpretation" && (
          product.interpretation_data ? (
            <div className="space-y-3">
              {Object.entries(product.interpretation_data).map(([key, val]) => (
                <div key={key}>
                  <label className="text-xs text-ink-muted">{key}</label>
                  <p className="text-sm text-ink">{String(val)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-ink-muted">Aguardando analise (Fase 2)</p>
          )
        )}

        {tab === "application" && (
          product.application_data ? (
            <div className="space-y-3">
              {Object.entries(product.application_data).map(([key, val]) => (
                <div key={key}>
                  <label className="text-xs text-ink-muted">{key}</label>
                  <p className="text-sm text-ink">{String(val)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-ink-muted">Aguardando analise da Moon (Fase 2)</p>
          )
        )}

        {tab === "decision" && (
          product.decision_data ? (
            <div className="space-y-3">
              {Object.entries(product.decision_data).map(([key, val]) => (
                <div key={key}>
                  <label className="text-xs text-ink-muted">{key}</label>
                  <p className="text-sm text-ink">{String(val)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-ink-muted">Aguardando analise da Moon (Fase 2)</p>
          )
        )}

        {tab === "history" && id && <RevisionTimeline productId={id} />}
      </div>

      {/* Pending changes */}
      {Object.keys(pendingChanges).length > 0 && (
        <div className="rounded-xl border border-amber/30 bg-amber/5 p-4">
          <p className="mb-2 text-sm font-medium text-amber">Alteracoes pendentes:</p>
          {Object.entries(pendingChanges).map(([field, { old: o, new: n }]) => (
            <p key={field} className="text-xs text-ink-muted">{field}: "{o}" → "{n}"</p>
          ))}
          <button onClick={handleSave} disabled={saving}
            className="mt-3 rounded-lg bg-ink px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50">
            {saving ? "Salvando..." : "Salvar alteracoes"}
          </button>
        </div>
      )}

      {/* Footer: status dropdowns */}
      <div className="flex items-center gap-4 rounded-xl border border-cream-dark bg-white p-4">
        <div>
          <label className="text-xs text-ink-muted">Editorial</label>
          <select value={product.status_editorial || "pendente"}
            onChange={(e) => handleStatusChange("status_editorial", e.target.value)}
            className="ml-2 rounded border border-cream-dark bg-cream px-2 py-1 text-sm">
            <option value="pendente">Pendente</option>
            <option value="em_revisao">Em revisao</option>
            <option value="aprovado">Aprovado</option>
            <option value="corrigido">Corrigido</option>
            <option value="rejeitado">Rejeitado</option>
          </select>
        </div>
        {isAdmin && (
          <div>
            <label className="text-xs text-ink-muted">Publicacao</label>
            <select value={product.status_publicacao || "rascunho"}
              onChange={(e) => handleStatusChange("status_publicacao", e.target.value)}
              className="ml-2 rounded border border-cream-dark bg-cream px-2 py-1 text-sm">
              <option value="rascunho">Rascunho</option>
              <option value="publicado">Publicado</option>
              <option value="despublicado">Despublicado</option>
              <option value="arquivado">Arquivado</option>
            </select>
          </div>
        )}
        <span className="ml-auto text-sm text-ink-muted">Confianca: {product.confidence ?? 0}%</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add route for product detail in App.tsx**

In Task 17, when adding ops routes, include:

```tsx
<Route path="products/:id" element={<OpsProductDetail />} />
```

Import: `import OpsProductDetail from "./pages/ops/OpsProductDetail";`

- [ ] **Step 3: Add GET /api/ops/products/{product_id} to ops.py backend**

Add to `src/api/routes/ops.py` (after the batch endpoint, before the parameterized PATCH):

```python
@router.get("/products/{product_id}")
def ops_get_product(
    product_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    product = session.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "id": product.id, "product_name": product.product_name, "brand_slug": product.brand_slug,
        "description": product.description, "usage_instructions": product.usage_instructions,
        "product_category": product.product_category, "verification_status": product.verification_status,
        "inci_ingredients": product.inci_ingredients, "image_url_main": product.image_url_main,
        "status_operacional": product.status_operacional, "status_editorial": product.status_editorial,
        "status_publicacao": product.status_publicacao, "confidence": product.confidence,
        "confidence_factors": product.confidence_factors,
        "interpretation_data": product.interpretation_data,
        "application_data": product.application_data,
        "decision_data": product.decision_data,
        "assigned_to": product.assigned_to,
    }
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ops/OpsProductDetail.tsx src/api/routes/ops.py
git commit -m "feat(ops): add product detail page with 4 tabs, inline edit, and revision history"
```

---

### Task 21: Ops Review page with flow contínuo

**Files:**
- Modify: `frontend/src/pages/ops/OpsReview.tsx`

- [ ] **Step 1: Implement review page with flow contínuo**

```tsx
// frontend/src/pages/ops/OpsReview.tsx
import { useState } from "react";
import { useAPI } from "../../hooks/useAPI";
import { getReviewQueue, startReview, resolveReview } from "../../lib/ops-api";
import type { ReviewQueueResponse, ReviewQueueItem } from "../../types/ops";

export default function OpsReview() {
  const [page, setPage] = useState(1);
  const [flowMode, setFlowMode] = useState(false);
  const [currentItem, setCurrentItem] = useState<ReviewQueueItem | null>(null);
  const [sessionCount, setSessionCount] = useState(0);
  const [notes, setNotes] = useState("");

  const { data, loading, refetch } = useAPI<ReviewQueueResponse>(
    () => getReviewQueue({ page }),
    [page],
  );

  const enterFlow = async (item: ReviewQueueItem) => {
    await startReview(item.id);
    setCurrentItem(item);
    setFlowMode(true);
    setNotes("");
  };

  const handleResolve = async (decision: string) => {
    if (!currentItem) return;
    await resolveReview(currentItem.id, decision, notes || undefined);
    setSessionCount((c) => c + 1);
    setNotes("");

    // Load next item
    const updated = await getReviewQueue({ page: 1 });
    if (updated.items.length > 0) {
      const next = updated.items[0];
      await startReview(next.id);
      setCurrentItem(next);
    } else {
      setFlowMode(false);
      setCurrentItem(null);
    }
    refetch();
  };

  if (flowMode && currentItem) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-ink">Revisao — Fluxo Continuo</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-ink-muted">{sessionCount} revisados nesta sessao</span>
            <button
              onClick={() => { setFlowMode(false); setCurrentItem(null); refetch(); }}
              className="rounded-lg border border-cream-dark px-3 py-1.5 text-xs text-ink-muted hover:bg-cream"
            >
              Sair do fluxo
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-cream-dark bg-white p-6">
          <h2 className="text-lg font-medium text-ink">{currentItem.product_name}</h2>
          <p className="text-sm text-ink-muted">{currentItem.brand_slug} · Confianca: {currentItem.confidence}%</p>
          <p className="mt-1 text-xs text-ink-faint">Status: {currentItem.status_editorial} · {currentItem.verification_status}</p>

          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notas (opcional)..."
            className="mt-4 w-full rounded-lg border border-cream-dark bg-cream p-3 text-sm outline-none"
            rows={2}
          />

          <div className="mt-4 flex gap-3">
            <button
              onClick={() => handleResolve("approve")}
              className="rounded-lg bg-sage/10 px-4 py-2 text-sm font-medium text-sage hover:bg-sage/20"
            >
              Aprovar
            </button>
            <button
              onClick={() => handleResolve("correct")}
              className="rounded-lg bg-amber/10 px-4 py-2 text-sm font-medium text-amber hover:bg-amber/20"
            >
              Corrigir e Aprovar
            </button>
            <button
              onClick={() => handleResolve("reject")}
              className="rounded-lg bg-coral/10 px-4 py-2 text-sm font-medium text-coral hover:bg-coral/20"
            >
              Rejeitar
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ink">Fila de Revisao</h1>
        <span className="text-sm text-ink-muted">{data?.total ?? 0} pendentes</span>
      </div>

      {loading ? (
        <p className="text-ink-muted">Carregando...</p>
      ) : (
        <div className="space-y-2">
          {data?.items.map((item) => (
            <button
              key={item.id}
              onClick={() => enterFlow(item)}
              className="flex w-full items-center justify-between rounded-xl border border-cream-dark bg-white px-4 py-3 text-left transition-colors hover:bg-cream"
            >
              <div>
                <p className="text-sm font-medium text-ink">{item.product_name}</p>
                <p className="text-xs text-ink-muted">{item.brand_slug} · {item.status_editorial}</p>
              </div>
              <span className="text-sm text-ink-muted">{item.confidence}%</span>
            </button>
          ))}

          {data?.items.length === 0 && (
            <p className="py-8 text-center text-sm text-ink-muted">Nenhum item pendente</p>
          )}

          {(data?.total ?? 0) > 20 && (
            <div className="flex justify-center gap-2 pt-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className="text-sm text-ink-muted hover:text-ink disabled:opacity-50">Anterior</button>
              <span className="text-sm text-ink-muted">Pagina {page}</span>
              <button onClick={() => setPage((p) => p + 1)}
                className="text-sm text-ink-muted hover:text-ink">Proxima</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ops/OpsReview.tsx
git commit -m "feat(ops): implement review queue with flow continuo mode"
```

---

### Task 21: Ops Ingredients page

**Files:**
- Modify: `frontend/src/pages/ops/OpsIngredients.tsx`

- [ ] **Step 1: Implement ingredients page with gaps view**

```tsx
// frontend/src/pages/ops/OpsIngredients.tsx
import { useState } from "react";
import { useAPI } from "../../hooks/useAPI";
import { fetchIngredients } from "../../lib/api";
import { getIngredientGaps, opsUpdateIngredient } from "../../lib/ops-api";
import type { IngredientGaps } from "../../types/ops";

export default function OpsIngredients() {
  const [tab, setTab] = useState<"list" | "gaps">("gaps");
  const [search, setSearch] = useState("");

  const { data: gaps, loading: gapsLoading, refetch: refetchGaps } = useAPI<IngredientGaps>(
    () => getIngredientGaps(),
    [],
  );

  const { data: ingredients, loading: listLoading } = useAPI(
    () => (search.length >= 2 ? fetchIngredients(search) : Promise.resolve([])),
    [search],
  );

  const handleCategorize = async (id: string, category: string) => {
    await opsUpdateIngredient(id, { category });
    refetchGaps();
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-ink">Ingredientes</h1>

      <div className="flex gap-2">
        <button
          onClick={() => setTab("gaps")}
          className={`rounded-lg px-3 py-1.5 text-sm ${tab === "gaps" ? "bg-ink text-white" : "bg-cream text-ink-muted"}`}
        >
          Gaps ({gaps ? gaps.uncategorized.length + gaps.orphan_raw_names.length : "..."})
        </button>
        <button
          onClick={() => setTab("list")}
          className={`rounded-lg px-3 py-1.5 text-sm ${tab === "list" ? "bg-ink text-white" : "bg-cream text-ink-muted"}`}
        >
          Buscar
        </button>
      </div>

      {tab === "gaps" && (
        <div className="space-y-6">
          {gapsLoading ? (
            <p className="text-ink-muted">Carregando...</p>
          ) : (
            <>
              {gaps && gaps.uncategorized.length > 0 && (
                <div>
                  <h2 className="mb-2 text-sm font-medium text-ink-muted">Sem categoria ({gaps.uncategorized.length})</h2>
                  <div className="space-y-1">
                    {gaps.uncategorized.map((ing) => (
                      <div key={ing.id} className="flex items-center justify-between rounded-lg border border-cream-dark bg-white px-4 py-2 text-sm">
                        <span className="text-ink">{ing.canonical_name}</span>
                        <select
                          defaultValue=""
                          onChange={(e) => e.target.value && handleCategorize(ing.id, e.target.value)}
                          className="rounded border border-cream-dark bg-cream px-2 py-1 text-xs"
                        >
                          <option value="">Categorizar...</option>
                          <option value="surfactant">Surfactante</option>
                          <option value="emollient">Emoliente</option>
                          <option value="humectant">Umectante</option>
                          <option value="preservative">Conservante</option>
                          <option value="fragrance">Fragrancia</option>
                          <option value="solvent">Solvente</option>
                          <option value="protein">Proteina</option>
                          <option value="silicone">Silicone</option>
                          <option value="other">Outro</option>
                        </select>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {gaps && gaps.orphan_raw_names.length > 0 && (
                <div>
                  <h2 className="mb-2 text-sm font-medium text-ink-muted">Orfaos ({gaps.orphan_raw_names.length})</h2>
                  <div className="space-y-1">
                    {gaps.orphan_raw_names.map((o) => (
                      <div key={o.raw_name} className="flex items-center justify-between rounded-lg border border-cream-dark bg-white px-4 py-2 text-sm">
                        <span className="text-ink">{o.raw_name}</span>
                        <span className="text-xs text-ink-muted">{o.product_count} produtos</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {tab === "list" && (
        <div className="space-y-4">
          <input
            type="text"
            placeholder="Buscar ingrediente..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full max-w-md rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm outline-none focus:border-ink"
          />
          {listLoading ? (
            <p className="text-ink-muted">Buscando...</p>
          ) : (
            <div className="space-y-1">
              {(ingredients || []).map((ing: any) => (
                <div key={ing.id} className="flex items-center justify-between rounded-lg border border-cream-dark bg-white px-4 py-2 text-sm">
                  <span className="text-ink">{ing.canonical_name}</span>
                  <span className="text-xs text-ink-muted">{ing.category || "sem categoria"}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ops/OpsIngredients.tsx
git commit -m "feat(ops): implement ingredients governance page with gaps view"
```

---

### Task 22: Ops Settings page (user management)

**Files:**
- Modify: `frontend/src/pages/ops/OpsSettings.tsx`

- [ ] **Step 1: Implement settings page**

```tsx
// frontend/src/pages/ops/OpsSettings.tsx
import { useState } from "react";
import { createUser, getUsers } from "../../lib/ops-api";
import { useAPI } from "../../hooks/useAPI";
import { useAuth } from "../../lib/auth";
import { Navigate } from "react-router-dom";
import type { OpsUser } from "../../types/ops";

export default function OpsSettings() {
  const { isAdmin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("reviewer");
  const [message, setMessage] = useState("");
  const { data: users, refetch } = useAPI<OpsUser[]>(() => getUsers(), []);

  if (!isAdmin) return <Navigate to="/ops" replace />;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const user = await createUser({ email, password, name, role });
      setMessage(`Usuario ${user.email} criado com sucesso`);
      setEmail("");
      setPassword("");
      setName("");
      refetch();
    } catch (err: any) {
      setMessage(err.message || "Erro ao criar usuario");
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-ink">Settings</h1>

      <div className="max-w-md rounded-xl border border-cream-dark bg-white p-6">
        <h2 className="mb-4 text-sm font-medium text-ink">Criar usuario</h2>
        <form onSubmit={handleCreate} className="space-y-3">
          <input type="text" placeholder="Nome" value={name} onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm outline-none" required />
          <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm outline-none" required />
          <input type="password" placeholder="Senha" value={password} onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm outline-none" required />
          <select value={role} onChange={(e) => setRole(e.target.value)}
            className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm">
            <option value="reviewer">Reviewer</option>
            <option value="admin">Admin</option>
          </select>
          <button type="submit" className="w-full rounded-lg bg-ink py-2 text-sm font-medium text-white hover:opacity-90">
            Criar
          </button>
        </form>
        {message && <p className="mt-3 text-sm text-ink-muted">{message}</p>}
      </div>

      {/* User list */}
      {users && users.length > 0 && (
        <div className="max-w-md rounded-xl border border-cream-dark bg-white p-6">
          <h2 className="mb-4 text-sm font-medium text-ink">Usuarios ({users.length})</h2>
          <div className="space-y-2">
            {users.map((u) => (
              <div key={u.id} className="flex items-center justify-between rounded-lg bg-cream px-3 py-2 text-sm">
                <div>
                  <span className="text-ink">{u.name}</span>
                  <span className="ml-2 text-ink-muted">{u.email}</span>
                </div>
                <span className="rounded-full bg-white px-2 py-0.5 text-xs text-ink-muted">{u.role}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ops/OpsSettings.tsx
git commit -m "feat(ops): implement settings page with user creation"
```

---

### Task 23: Revision timeline component

**Files:**
- Create: `frontend/src/components/ops/RevisionTimeline.tsx`

- [ ] **Step 1: Create revision timeline component**

```tsx
// frontend/src/components/ops/RevisionTimeline.tsx
import { useAPI } from "../../hooks/useAPI";
import { getProductHistory } from "../../lib/ops-api";
import type { RevisionEntry } from "../../types/ops";

export function RevisionTimeline({ productId }: { productId: string }) {
  const { data, loading } = useAPI<{ revisions: RevisionEntry[] }>(
    () => getProductHistory(productId),
    [productId],
  );

  if (loading) return <p className="text-xs text-ink-muted">Carregando historico...</p>;
  if (!data || data.revisions.length === 0) return <p className="text-xs text-ink-muted">Sem alteracoes registradas</p>;

  return (
    <div className="space-y-3">
      {data.revisions.map((r) => (
        <div key={r.revision_id} className="border-l-2 border-cream-dark pl-4">
          <p className="text-sm text-ink">
            <span className="font-medium">{r.field_name}</span>
            {r.old_value && <span className="text-ink-muted"> de "{r.old_value}"</span>}
            <span className="text-ink-muted"> para </span>
            <span className="font-medium">"{r.new_value}"</span>
          </p>
          <p className="text-xs text-ink-faint">
            {r.change_source} · {new Date(r.created_at).toLocaleString("pt-BR")}
            {r.change_reason && ` · ${r.change_reason}`}
          </p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ops/RevisionTimeline.tsx
git commit -m "feat(ops): add revision timeline component"
```

---

### Task 24: Seed admin user via CLI

**Files:**
- This is a one-time setup step, not a code task

- [ ] **Step 1: Create seed script or CLI command**

Add a simple script to seed the first admin user:

```python
# scripts/seed_admin.py
"""Seed the first admin user. Run once after migration."""
from __future__ import annotations
import bcrypt
from sqlalchemy.orm import Session
from src.storage.database import get_engine
from src.storage.ops_models import UserORM

engine = get_engine()
pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()

with Session(engine) as s:
    existing = s.query(UserORM).filter(UserORM.email == "admin@haira.com").first()
    if existing:
        print(f"Admin already exists: {existing.user_id}")
    else:
        user = UserORM(email="admin@haira.com", password_hash=pw, name="Admin", role="admin")
        s.add(user)
        s.commit()
        print(f"Admin created: {user.user_id}")
```

- [ ] **Step 2: Run seed**

Run: `python scripts/seed_admin.py`
Expected: "Admin created: <uuid>"

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_admin.py
git commit -m "chore: add admin seed script"
```

---

### Task 25: Final integration test and build verification

- [ ] **Step 1: Run full backend test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Run frontend lint**

Run: `cd frontend && npm run lint`
Expected: No new errors from our changes

- [ ] **Step 4: Manual smoke test**

Start both servers:
- Terminal 1: `uvicorn src.api.main:app --reload --port 8000`
- Terminal 2: `cd frontend && npm run dev`

Verify:
1. Public routes (`/`, `/brands`, `/explorer`) still work
2. `/login` shows login form
3. Login with admin@haira.com / admin123
4. `/ops` shows dashboard with KPIs
5. `/ops/products` shows product table
6. `/ops/review` shows review queue
7. `/ops/ingredients` shows gaps (admin only)
8. `/ops/settings` shows user creation form

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: integration fixes for ops panel v1"
```
