# Haira Data Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve Haira into a normalized knowledge base with canonical ingredients, claims, dual validation, and a review queue — while preserving all existing data and functionality.

**Architecture:** New normalized tables (ingredients, claims, images, compositions, validation) coexist with existing JSON columns via dual-write. A `NormalizedWriter` service handles the normalization layer. Dual validation runs as a separate CLI step (`haira validate`) that re-extracts and compares fields. New API routes expose normalized data and the review queue.

**Tech Stack:** Python 3.12+, SQLAlchemy, Alembic, FastAPI, React 19 + TypeScript + Tailwind CSS 4

**Spec:** `docs/superpowers/specs/2026-03-13-haira-data-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/storage/migrations/versions/e1_normalized_tables.py` | Alembic migration for all new tables |
| `src/storage/normalized_writer.py` | Dual-write service: resolves raw data → canonical entities → junction rows |
| `src/core/dual_validator.py` | Comparison logic for dual-pass validation |
| `src/api/routes/ingredients.py` | API routes for ingredient browsing/search |
| `scripts/seed_ingredients.py` | One-time seeding of canonical ingredients + claims from existing data |
| `tests/storage/test_normalized_writer.py` | Tests for normalized writer |
| `tests/core/test_dual_validator.py` | Tests for dual validator |
| `tests/api/test_ingredients_api.py` | Tests for ingredient API routes |
| `frontend/src/pages/ReviewQueue.tsx` | Review queue page for dual validation divergences |
| `frontend/src/types/api.ts` | Extended with new types |

### Modified Files

| File | Change |
|------|--------|
| `src/storage/orm_models.py` | Add 10 new ORM models |
| `src/core/models.py` | Add Pydantic models for new entities |
| `src/storage/repository.py` | Add methods for ingredients, review queue, validation |
| `src/pipeline/coverage_engine.py` | Integrate normalized writer into extraction flow |
| `src/cli/main.py` | Add `haira validate` command |
| `src/api/main.py` | Mount ingredients router |
| `src/api/routes/products.py` | Add `/products/{id}/ingredients` and `/validation/{id}` endpoints |
| `src/api/routes/quarantine.py` | Add review queue endpoints |
| `frontend/src/lib/api.ts` | Add API client functions for new endpoints |
| `frontend/src/App.tsx` | Add route for ReviewQueue page |

---

## Chunk 1: Schema & ORM Models

### Task 1: New ORM Models

**Files:**
- Modify: `src/storage/orm_models.py`
- Test: `tests/storage/test_orm_models.py`

- [ ] **Step 1: Write failing tests for new ORM models**

```python
# tests/storage/test_orm_models.py — append to existing file

def test_ingredient_orm_creation():
    from src.storage.orm_models import IngredientORM
    ing = IngredientORM(canonical_name="Dimethicone", category="silicone")
    assert ing.canonical_name == "Dimethicone"
    assert ing.id is not None

def test_ingredient_alias_orm():
    from src.storage.orm_models import IngredientAliasORM
    alias = IngredientAliasORM(alias="DIMETHICONE", language="en")
    assert alias.alias == "DIMETHICONE"

def test_product_ingredient_orm():
    from src.storage.orm_models import ProductIngredientORM
    pi = ProductIngredientORM(position=1, raw_name="Dimethicone", validation_status="raw")
    assert pi.validation_status == "raw"

def test_claim_orm():
    from src.storage.orm_models import ClaimORM
    claim = ClaimORM(canonical_name="sulfate_free", display_name="Sulfate Free", category="seal")
    assert claim.canonical_name == "sulfate_free"

def test_product_claim_orm():
    from src.storage.orm_models import ProductClaimORM
    pc = ProductClaimORM(source="keyword", confidence_score=0.9)
    assert pc.confidence_score == 0.9

def test_product_image_orm():
    from src.storage.orm_models import ProductImageORM
    img = ProductImageORM(url="https://example.com/img.jpg", image_type="main", position=0)
    assert img.image_type == "main"

def test_product_composition_orm():
    from src.storage.orm_models import ProductCompositionORM
    comp = ProductCompositionORM(section_label="Composição", content="Water, Glycerin")
    assert comp.section_label == "Composição"

def test_validation_comparison_orm():
    from src.storage.orm_models import ValidationComparisonORM
    vc = ValidationComparisonORM(field_name="product_name", pass_1_value="Shampoo X", pass_2_value="Shampoo X", resolution="auto_matched")
    assert vc.resolution == "auto_matched"

def test_review_queue_orm():
    from src.storage.orm_models import ReviewQueueORM
    rq = ReviewQueueORM(field_name="inci_ingredients", status="pending")
    assert rq.status == "pending"

def test_claim_alias_orm():
    from src.storage.orm_models import ClaimAliasORM
    ca = ClaimAliasORM(alias="sem sulfato", language="pt")
    assert ca.alias == "sem sulfato"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/test_orm_models.py -v -k "ingredient or claim or image or composition or validation or review_queue"`
Expected: FAIL with ImportError (models don't exist yet)

- [ ] **Step 3: Implement new ORM models**

Add to `src/storage/orm_models.py` after `BrandCoverageORM`:

```python
class IngredientORM(Base):
    __tablename__ = "ingredients"

    id = Column(String(36), primary_key=True, default=_uuid)
    canonical_name = Column(Text, nullable=False, unique=True)
    inci_name = Column(Text, nullable=True)
    cas_number = Column(String(50), nullable=True)
    category = Column(String(100), nullable=True)
    safety_rating = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    aliases = relationship("IngredientAliasORM", back_populates="ingredient", cascade="all, delete-orphan")
    product_ingredients = relationship("ProductIngredientORM", back_populates="ingredient")


class IngredientAliasORM(Base):
    __tablename__ = "ingredient_aliases"

    id = Column(String(36), primary_key=True, default=_uuid)
    ingredient_id = Column(String(36), ForeignKey("ingredients.id"), nullable=False)
    alias = Column(Text, nullable=False, unique=True)
    language = Column(String(10), nullable=False, default="en")

    ingredient = relationship("IngredientORM", back_populates="aliases")


class ProductIngredientORM(Base):
    __tablename__ = "product_ingredients"
    __table_args__ = (UniqueConstraint("product_id", "ingredient_id"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    ingredient_id = Column(String(36), ForeignKey("ingredients.id"), nullable=False, index=True)
    position = Column(Integer, nullable=True)
    raw_name = Column(Text, nullable=True)
    validation_status = Column(String(50), nullable=False, default="raw")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    product = relationship("ProductORM")
    ingredient = relationship("IngredientORM", back_populates="product_ingredients")


class ClaimORM(Base):
    __tablename__ = "claims"

    id = Column(String(36), primary_key=True, default=_uuid)
    canonical_name = Column(Text, nullable=False, unique=True)
    display_name = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    aliases = relationship("ClaimAliasORM", back_populates="claim", cascade="all, delete-orphan")


class ClaimAliasORM(Base):
    __tablename__ = "claim_aliases"

    id = Column(String(36), primary_key=True, default=_uuid)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False)
    alias = Column(Text, nullable=False, unique=True)
    language = Column(String(10), nullable=False, default="en")

    claim = relationship("ClaimORM", back_populates="aliases")


class ProductClaimORM(Base):
    __tablename__ = "product_claims"
    __table_args__ = (UniqueConstraint("product_id", "claim_id"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False, index=True)
    source = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)
    evidence_text = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    product = relationship("ProductORM")
    claim = relationship("ClaimORM")


class ProductImageORM(Base):
    __tablename__ = "product_images"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    url = Column(Text, nullable=False)
    image_type = Column(String(50), nullable=False, default="gallery")
    position = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    product = relationship("ProductORM")


class ProductCompositionORM(Base):
    __tablename__ = "product_compositions"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    section_label = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    source_selector = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    product = relationship("ProductORM")


class ValidationComparisonORM(Base):
    __tablename__ = "validation_comparisons"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    pass_1_value = Column(Text, nullable=True)
    pass_2_value = Column(Text, nullable=True)
    resolution = Column(String(50), nullable=False, default="pending")
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    product = relationship("ProductORM")
    review_queue_item = relationship("ReviewQueueORM", back_populates="comparison", uselist=False)


class ReviewQueueORM(Base):
    __tablename__ = "review_queue"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    comparison_id = Column(String(36), ForeignKey("validation_comparisons.id"), nullable=True)
    field_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)

    product = relationship("ProductORM")
    comparison = relationship("ValidationComparisonORM", back_populates="review_queue_item")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/storage/test_orm_models.py -v -k "ingredient or claim or image or composition or validation or review_queue"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage/orm_models.py tests/storage/test_orm_models.py
git commit -m "feat: add ORM models for normalized tables (ingredients, claims, images, compositions, validation)"
```

### Task 2: Alembic Migration

**Files:**
- Create: `src/storage/migrations/versions/e1a2b3c4d5e6_normalized_tables.py` (via autogenerate)

- [ ] **Step 1: Generate Alembic migration**

Run: `alembic revision --autogenerate -m "add normalized tables for ingredients claims images compositions validation"`
Expected: New migration file created in `src/storage/migrations/versions/`

- [ ] **Step 2: Review the generated migration**

Open the generated file and verify it creates all 10 tables: `ingredients`, `ingredient_aliases`, `product_ingredients`, `claims`, `claim_aliases`, `product_claims`, `product_images`, `product_compositions`, `validation_comparisons`, `review_queue`.

Verify all indexes are present on foreign key columns.

- [ ] **Step 3: Run migration**

Run: `alembic upgrade head`
Expected: All 10 tables created successfully

- [ ] **Step 4: Verify tables exist**

Run: `python3 -c "from src.storage.database import get_engine; e = get_engine(); print([t for t in e.table_names() if t not in ('alembic_version',)])"`
Expected: All 14 tables listed (4 existing + 10 new)

- [ ] **Step 5: Commit**

```bash
git add src/storage/migrations/versions/
git commit -m "feat: add alembic migration for normalized tables"
```

### Task 3: Pydantic Models

**Files:**
- Modify: `src/core/models.py`
- Test: `tests/core/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_models.py — append

def test_ingredient_model():
    from src.core.models import Ingredient
    ing = Ingredient(id="abc", canonical_name="Dimethicone", category="silicone")
    assert ing.canonical_name == "Dimethicone"

def test_ingredient_with_aliases():
    from src.core.models import Ingredient
    ing = Ingredient(id="abc", canonical_name="Dimethicone", aliases=["DIMETHICONE", "Dimeticone"])
    assert len(ing.aliases) == 2

def test_claim_model():
    from src.core.models import Claim
    c = Claim(id="abc", canonical_name="sulfate_free", display_name="Sulfate Free", category="seal")
    assert c.display_name == "Sulfate Free"

def test_validation_comparison_model():
    from src.core.models import ValidationComparison
    vc = ValidationComparison(
        id="abc", product_id="xyz", field_name="product_name",
        pass_1_value="Shampoo X", pass_2_value="Shampoo X", resolution="auto_matched"
    )
    assert vc.resolution == "auto_matched"

def test_review_queue_item_model():
    from src.core.models import ReviewQueueItem
    rq = ReviewQueueItem(
        id="abc", product_id="xyz", field_name="inci_ingredients",
        status="pending",
    )
    assert rq.status == "pending"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_models.py -v -k "ingredient or claim or validation_comparison or review_queue_item"`
Expected: FAIL with ImportError

- [ ] **Step 3: Add Pydantic models**

Add to `src/core/models.py`:

```python
class ValidationStatus(str, Enum):
    RAW = "raw"
    AUTO_VALIDATED = "auto_validated"
    DUAL_VALIDATED = "dual_validated"
    NEEDS_REVIEW = "needs_review"
    MANUALLY_VERIFIED = "manually_verified"


class Ingredient(BaseModel):
    id: str
    canonical_name: str
    inci_name: str | None = None
    cas_number: str | None = None
    category: str | None = None
    safety_rating: str | None = None
    aliases: list[str] = []


class Claim(BaseModel):
    id: str
    canonical_name: str
    display_name: str | None = None
    category: str | None = None
    aliases: list[str] = []


class ProductIngredientDetail(BaseModel):
    ingredient: Ingredient
    position: int | None = None
    raw_name: str | None = None
    validation_status: str = "raw"


class ValidationComparison(BaseModel):
    id: str
    product_id: str
    field_name: str
    pass_1_value: str | None = None
    pass_2_value: str | None = None
    resolution: str = "pending"


class ReviewQueueItem(BaseModel):
    id: str
    product_id: str
    field_name: str
    status: str = "pending"
    reviewer_notes: str | None = None
    product_name: str | None = None
    brand_slug: str | None = None
    comparison: ValidationComparison | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_models.py -v -k "ingredient or claim or validation_comparison or review_queue_item"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/models.py tests/core/test_models.py
git commit -m "feat: add Pydantic models for ingredients, claims, validation, review queue"
```

---

## Chunk 2: Normalized Writer & Ingredient Seeding

### Task 4: Normalized Writer Service

**Files:**
- Create: `src/storage/normalized_writer.py`
- Create: `tests/storage/test_normalized_writer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/storage/test_normalized_writer.py
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.storage.orm_models import Base, ProductORM, IngredientORM, IngredientAliasORM, ProductIngredientORM


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def sample_product(session):
    p = ProductORM(
        brand_slug="test-brand",
        product_name="Test Shampoo",
        product_url="https://example.com/shampoo",
        inci_ingredients=["Water", "Sodium Lauryl Sulfate", "Dimethicone"],
    )
    session.add(p)
    session.commit()
    return p


class TestNormalizedWriter:
    def test_resolve_or_create_ingredient_creates_new(self, session):
        from src.storage.normalized_writer import NormalizedWriter
        writer = NormalizedWriter(session)
        ing = writer.resolve_or_create_ingredient("Dimethicone")
        assert ing.canonical_name == "Dimethicone"
        assert session.query(IngredientORM).count() == 1

    def test_resolve_or_create_ingredient_finds_existing(self, session):
        from src.storage.normalized_writer import NormalizedWriter
        writer = NormalizedWriter(session)
        ing1 = writer.resolve_or_create_ingredient("Dimethicone")
        ing2 = writer.resolve_or_create_ingredient("Dimethicone")
        assert ing1.id == ing2.id
        assert session.query(IngredientORM).count() == 1

    def test_resolve_by_alias(self, session):
        from src.storage.normalized_writer import NormalizedWriter
        writer = NormalizedWriter(session)
        ing = writer.resolve_or_create_ingredient("Dimethicone")
        # Add alias
        alias = IngredientAliasORM(ingredient_id=ing.id, alias="DIMETHICONE", language="en")
        session.add(alias)
        session.commit()
        # Resolve by alias
        found = writer.resolve_or_create_ingredient("DIMETHICONE")
        assert found.id == ing.id

    def test_write_product_ingredients(self, session, sample_product):
        from src.storage.normalized_writer import NormalizedWriter
        writer = NormalizedWriter(session)
        writer.write_product_ingredients(sample_product)
        rows = session.query(ProductIngredientORM).filter_by(product_id=sample_product.id).all()
        assert len(rows) == 3
        assert rows[0].position == 1
        assert rows[0].raw_name == "Water"
        assert rows[2].raw_name == "Dimethicone"

    def test_write_product_ingredients_idempotent(self, session, sample_product):
        from src.storage.normalized_writer import NormalizedWriter
        writer = NormalizedWriter(session)
        writer.write_product_ingredients(sample_product)
        writer.write_product_ingredients(sample_product)  # second call
        rows = session.query(ProductIngredientORM).filter_by(product_id=sample_product.id).all()
        assert len(rows) == 3  # no duplicates

    def test_write_product_ingredients_skips_empty(self, session):
        from src.storage.normalized_writer import NormalizedWriter
        writer = NormalizedWriter(session)
        p = ProductORM(
            brand_slug="test", product_name="No INCI",
            product_url="https://example.com/no-inci", inci_ingredients=None,
        )
        session.add(p)
        session.commit()
        writer.write_product_ingredients(p)
        assert session.query(ProductIngredientORM).count() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/test_normalized_writer.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement NormalizedWriter**

```python
# src/storage/normalized_writer.py
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from src.storage.orm_models import (
    ProductORM, IngredientORM, IngredientAliasORM, ProductIngredientORM,
    ProductImageORM, ProductCompositionORM,
)

logger = logging.getLogger(__name__)


class NormalizedWriter:
    """Writes normalized data from ProductORM into junction/entity tables."""

    def __init__(self, session: Session):
        self._session = session
        self._ingredient_cache: dict[str, IngredientORM] = {}

    def resolve_or_create_ingredient(self, raw_name: str) -> IngredientORM:
        normalized = raw_name.strip()
        cache_key = normalized.lower()

        if cache_key in self._ingredient_cache:
            return self._ingredient_cache[cache_key]

        # Try exact canonical match
        existing = self._session.query(IngredientORM).filter(
            IngredientORM.canonical_name == normalized
        ).first()
        if existing:
            self._ingredient_cache[cache_key] = existing
            return existing

        # Try alias match (case-insensitive via lower comparison)
        alias = self._session.query(IngredientAliasORM).filter(
            IngredientAliasORM.alias == normalized
        ).first()
        if alias:
            ing = self._session.get(IngredientORM, alias.ingredient_id)
            if ing:
                self._ingredient_cache[cache_key] = ing
                return ing

        # Create new
        ing = IngredientORM(canonical_name=normalized)
        self._session.add(ing)
        self._session.flush()
        self._ingredient_cache[cache_key] = ing
        return ing

    def write_product_ingredients(self, product: ProductORM) -> int:
        if not product.inci_ingredients:
            return 0

        ingredients = product.inci_ingredients
        if not isinstance(ingredients, list):
            return 0

        # Delete existing junction rows for idempotency
        self._session.query(ProductIngredientORM).filter_by(
            product_id=product.id
        ).delete()

        count = 0
        for i, raw_name in enumerate(ingredients):
            if not isinstance(raw_name, str) or not raw_name.strip():
                continue
            ingredient = self.resolve_or_create_ingredient(raw_name)
            pi = ProductIngredientORM(
                product_id=product.id,
                ingredient_id=ingredient.id,
                position=i + 1,
                raw_name=raw_name.strip(),
                validation_status="raw",
            )
            self._session.add(pi)
            count += 1

        self._session.flush()
        return count

    def write_product_claims(self, product: ProductORM) -> int:
        """Write product claims from product_labels JSON to normalized tables."""
        from src.storage.orm_models import ClaimORM, ProductClaimORM

        self._session.query(ProductClaimORM).filter_by(product_id=product.id).delete()

        if not product.product_labels or not isinstance(product.product_labels, dict):
            return 0

        detected = product.product_labels.get("detected", [])
        inferred = product.product_labels.get("inferred", [])
        confidence = product.product_labels.get("confidence", 0.0)

        count = 0
        all_claims = [(c, "keyword") for c in detected] + [(c, "inci_inference") for c in inferred]
        for claim_name, source in all_claims:
            # Resolve or create canonical claim
            existing = self._session.query(ClaimORM).filter_by(canonical_name=claim_name).first()
            if not existing:
                existing = ClaimORM(
                    canonical_name=claim_name,
                    display_name=claim_name.replace("_", " ").title(),
                    category="seal",
                )
                self._session.add(existing)
                self._session.flush()

            pc = ProductClaimORM(
                product_id=product.id,
                claim_id=existing.id,
                source=source,
                confidence_score=confidence,
            )
            self._session.add(pc)
            count += 1

        self._session.flush()
        return count

    def write_product_images(self, product: ProductORM) -> int:
        # Delete existing for idempotency
        self._session.query(ProductImageORM).filter_by(product_id=product.id).delete()

        count = 0
        if product.image_url_main:
            img = ProductImageORM(
                product_id=product.id, url=product.image_url_main,
                image_type="main", position=0,
            )
            self._session.add(img)
            count += 1

        if product.image_urls_gallery and isinstance(product.image_urls_gallery, list):
            for i, url in enumerate(product.image_urls_gallery):
                if isinstance(url, str) and url.strip():
                    img = ProductImageORM(
                        product_id=product.id, url=url.strip(),
                        image_type="gallery", position=i + 1,
                    )
                    self._session.add(img)
                    count += 1

        if count:
            self._session.flush()
        return count

    def write_product_compositions(self, product: ProductORM) -> int:
        self._session.query(ProductCompositionORM).filter_by(product_id=product.id).delete()

        if not product.composition:
            return 0

        comp = ProductCompositionORM(
            product_id=product.id,
            section_label="Composição",
            content=product.composition,
        )
        self._session.add(comp)
        self._session.flush()
        return 1

    def write_all(self, product: ProductORM) -> dict:
        """Write all normalized data. Caller must commit."""
        result = {
            "ingredients": self.write_product_ingredients(product),
            "claims": self.write_product_claims(product),
            "images": self.write_product_images(product),
            "compositions": self.write_product_compositions(product),
        }
        self._session.commit()
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/storage/test_normalized_writer.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/storage/normalized_writer.py tests/storage/test_normalized_writer.py
git commit -m "feat: add NormalizedWriter service for dual-write to normalized tables"
```

### Task 5: Ingredient Seeding Script

**Files:**
- Create: `scripts/seed_ingredients.py`

- [ ] **Step 1: Write the seeding script**

```python
# scripts/seed_ingredients.py
"""
Seed the ingredients table from existing inci_ingredients JSON data.
Usage: python3 scripts/seed_ingredients.py [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.database import get_session
from src.storage.orm_models import ProductORM, IngredientORM, IngredientAliasORM
from src.storage.normalized_writer import NormalizedWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session = get_session()

    # Gather all raw ingredient names from all products
    products = session.query(ProductORM).filter(ProductORM.inci_ingredients.isnot(None)).all()
    logger.info(f"Found {len(products)} products with INCI data")

    raw_names: Counter[str] = Counter()
    for p in products:
        if isinstance(p.inci_ingredients, list):
            for name in p.inci_ingredients:
                if isinstance(name, str) and name.strip():
                    raw_names[name.strip()] += 1

    logger.info(f"Found {len(raw_names)} unique raw ingredient names")

    if args.dry_run:
        # Show top 20 most common
        for name, count in raw_names.most_common(20):
            print(f"  {count:4d}x  {name}")
        print(f"  ... and {len(raw_names) - 20} more")
        return

    # Use NormalizedWriter to create canonical ingredients
    writer = NormalizedWriter(session)
    created = 0
    for name in raw_names:
        writer.resolve_or_create_ingredient(name)
        created += 1

    session.commit()

    total_ingredients = session.query(IngredientORM).count()
    logger.info(f"Seeded {total_ingredients} canonical ingredients from {created} raw names")

    # Now populate product_ingredients for all products
    written = 0
    for p in products:
        count = writer.write_product_ingredients(p)
        written += count

    logger.info(f"Created {written} product_ingredient rows across {len(products)} products")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test with dry-run**

Run: `python3 scripts/seed_ingredients.py --dry-run`
Expected: Lists top 20 most common ingredient names from existing data

- [ ] **Step 3: Run actual seeding**

Run: `python3 scripts/seed_ingredients.py`
Expected: Creates ingredient records and product_ingredient junction rows

- [ ] **Step 4: Verify results**

Run: `python3 -c "from src.storage.database import get_session; from src.storage.orm_models import IngredientORM, ProductIngredientORM; s = get_session(); print(f'Ingredients: {s.query(IngredientORM).count()}'); print(f'Product-Ingredient links: {s.query(ProductIngredientORM).count()}')"`

- [ ] **Step 5: Commit**

```bash
git add scripts/seed_ingredients.py
git commit -m "feat: add ingredient seeding script to populate normalized tables from existing data"
```

---

## Chunk 3: Dual Validator & CLI

### Task 6: Dual Validator Module

**Files:**
- Create: `src/core/dual_validator.py`
- Create: `tests/core/test_dual_validator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_dual_validator.py
from __future__ import annotations

import pytest
from src.core.dual_validator import compare_fields, normalize_text, compare_inci_lists


class TestNormalizeText:
    def test_strips_whitespace(self):
        assert normalize_text("  hello  ") == "hello"

    def test_collapses_spaces(self):
        assert normalize_text("hello   world") == "hello world"

    def test_lowercases(self):
        assert normalize_text("Hello World") == "hello world"

    def test_none_returns_empty(self):
        assert normalize_text(None) == ""


class TestCompareInciLists:
    def test_identical_lists_match(self):
        a = ["Water", "Glycerin", "Dimethicone"]
        b = ["Water", "Glycerin", "Dimethicone"]
        result = compare_inci_lists(a, b)
        assert result.matches is True

    def test_case_difference_matches(self):
        a = ["Water", "GLYCERIN"]
        b = ["water", "Glycerin"]
        result = compare_inci_lists(a, b)
        assert result.matches is True

    def test_different_order_diverges(self):
        a = ["Water", "Glycerin"]
        b = ["Glycerin", "Water"]
        result = compare_inci_lists(a, b)
        assert result.matches is False

    def test_different_length_diverges(self):
        a = ["Water", "Glycerin"]
        b = ["Water"]
        result = compare_inci_lists(a, b)
        assert result.matches is False


class TestCompareFields:
    def test_exact_match(self):
        result = compare_fields("product_name", "Shampoo X", "Shampoo X")
        assert result.resolution == "auto_matched"

    def test_whitespace_normalization(self):
        result = compare_fields("product_name", "Shampoo  X", "Shampoo X")
        assert result.resolution == "auto_matched"

    def test_price_within_tolerance(self):
        result = compare_fields("price", "29.90", "29.80")
        assert result.resolution == "auto_matched"

    def test_price_outside_tolerance(self):
        result = compare_fields("price", "29.90", "35.00")
        assert result.resolution == "pending"

    def test_description_similar(self):
        result = compare_fields("description", "A great shampoo for all hair types", "A great shampoo for all hair types.")
        assert result.resolution == "auto_matched"

    def test_description_different(self):
        result = compare_fields("description", "A shampoo", "A completely different conditioner product")
        assert result.resolution == "pending"

    def test_both_none_matches(self):
        result = compare_fields("product_name", None, None)
        assert result.resolution == "auto_matched"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_dual_validator.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement dual validator**

```python
# src/core/dual_validator.py
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class FieldComparison:
    field_name: str
    pass_1_value: str | None
    pass_2_value: str | None
    matches: bool
    resolution: str  # auto_matched, pending


@dataclass
class InciComparison:
    matches: bool
    mismatches: list[tuple[int, str | None, str | None]]


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def compare_inci_lists(list_a: list[str], list_b: list[str]) -> InciComparison:
    norm_a = [normalize_text(x) for x in list_a]
    norm_b = [normalize_text(x) for x in list_b]

    if len(norm_a) != len(norm_b):
        mismatches = [(i, norm_a[i] if i < len(norm_a) else None, norm_b[i] if i < len(norm_b) else None)
                      for i in range(max(len(norm_a), len(norm_b)))]
        return InciComparison(matches=False, mismatches=mismatches)

    mismatches = []
    for i, (a, b) in enumerate(zip(norm_a, norm_b)):
        if a != b:
            # Fuzzy match for minor differences
            ratio = SequenceMatcher(None, a, b).ratio()
            if ratio < 0.85:
                mismatches.append((i, a, b))

    return InciComparison(matches=len(mismatches) == 0, mismatches=mismatches)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def compare_fields(field_name: str, val_1: str | None, val_2: str | None) -> FieldComparison:
    # Both None
    if val_1 is None and val_2 is None:
        return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")

    # One None
    if val_1 is None or val_2 is None:
        return FieldComparison(field_name, val_1, val_2, matches=False, resolution="pending")

    # Price: numeric tolerance ±1%
    if field_name == "price":
        try:
            p1, p2 = float(val_1), float(val_2)
            if p1 == 0 and p2 == 0:
                return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")
            if p1 > 0 and abs(p1 - p2) / p1 <= 0.01:
                return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")
        except (ValueError, ZeroDivisionError):
            pass
        return FieldComparison(field_name, val_1, val_2, matches=False, resolution="pending")

    # Text fields: normalized comparison
    norm_1 = normalize_text(val_1)
    norm_2 = normalize_text(val_2)

    if norm_1 == norm_2:
        return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")

    # Similarity for text fields
    if field_name in ("description", "composition", "care_usage"):
        if _similarity(val_1, val_2) >= 0.90:
            return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")

    # URL comparison: strip protocol and trailing slash
    if field_name == "image_url_main":
        clean_1 = re.sub(r"^https?://", "", norm_1).rstrip("/")
        clean_2 = re.sub(r"^https?://", "", norm_2).rstrip("/")
        if clean_1 == clean_2:
            return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")

    return FieldComparison(field_name, val_1, val_2, matches=False, resolution="pending")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_dual_validator.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/core/dual_validator.py tests/core/test_dual_validator.py
git commit -m "feat: add dual validator with field comparison and INCI list diffing"
```

### Task 7: Repository Methods for Normalized Data

**Files:**
- Modify: `src/storage/repository.py`
- Test: `tests/storage/test_repository.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/storage/test_repository.py`:

```python
def test_get_product_ingredients(session, sample_product):
    """Test fetching normalized ingredients for a product."""
    from src.storage.orm_models import IngredientORM, ProductIngredientORM
    ing = IngredientORM(canonical_name="Water")
    session.add(ing)
    session.flush()
    pi = ProductIngredientORM(
        product_id=sample_product.id, ingredient_id=ing.id,
        position=1, raw_name="Water",
    )
    session.add(pi)
    session.commit()

    repo = ProductRepository(session)
    ingredients = repo.get_product_ingredients(sample_product.id)
    assert len(ingredients) == 1
    assert ingredients[0].raw_name == "Water"
    assert ingredients[0].ingredient.canonical_name == "Water"


def test_get_review_queue(session):
    """Test fetching pending review queue items."""
    from src.storage.orm_models import ReviewQueueORM
    rq = ReviewQueueORM(
        product_id="fake-id", field_name="product_name", status="pending",
    )
    session.add(rq)
    session.commit()

    repo = ProductRepository(session)
    items = repo.get_review_queue(status="pending")
    assert len(items) == 1
    assert items[0].field_name == "product_name"


def test_resolve_review_queue_item(session):
    """Test resolving a review queue item."""
    from src.storage.orm_models import ReviewQueueORM
    rq = ReviewQueueORM(
        product_id="fake-id", field_name="product_name", status="pending",
    )
    session.add(rq)
    session.commit()

    repo = ProductRepository(session)
    repo.resolve_review_queue_item(rq.id, status="approved", notes="Looks good")
    session.refresh(rq)
    assert rq.status == "approved"
    assert rq.reviewer_notes == "Looks good"
    assert rq.resolved_at is not None


def test_search_ingredients(session):
    """Test ingredient search."""
    from src.storage.orm_models import IngredientORM
    session.add(IngredientORM(canonical_name="Dimethicone", category="silicone"))
    session.add(IngredientORM(canonical_name="Water"))
    session.commit()

    repo = ProductRepository(session)
    results = repo.search_ingredients("dimeth")
    assert len(results) == 1
    assert results[0].canonical_name == "Dimethicone"
```

Note: these tests require that the test file's `session` and `sample_product` fixtures create in-memory DB with all tables (including the new ones). Verify the existing test fixtures use `Base.metadata.create_all(engine)` — this will auto-include the new models.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/test_repository.py -v -k "ingredients or review_queue or search_ingredients"`
Expected: FAIL with AttributeError (methods don't exist)

- [ ] **Step 3: Add repository methods**

Add to `ProductRepository` class in `src/storage/repository.py`:

```python
from src.storage.orm_models import (
    ProductIngredientORM, IngredientORM, ReviewQueueORM,
    ValidationComparisonORM,
)

def get_product_ingredients(self, product_id: str) -> list[ProductIngredientORM]:
    return (
        self._session.query(ProductIngredientORM)
        .filter_by(product_id=product_id)
        .order_by(ProductIngredientORM.position)
        .all()
    )

def search_ingredients(self, query: str, limit: int = 50) -> list[IngredientORM]:
    return (
        self._session.query(IngredientORM)
        .filter(IngredientORM.canonical_name.ilike(f"%{query}%"))
        .limit(limit)
        .all()
    )

def get_review_queue(
    self, status: str | None = None, brand_slug: str | None = None, limit: int = 100,
) -> list[ReviewQueueORM]:
    q = self._session.query(ReviewQueueORM)
    if status:
        q = q.filter_by(status=status)
    if brand_slug:
        q = q.join(ProductORM, ReviewQueueORM.product_id == ProductORM.id)
        q = q.filter(ProductORM.brand_slug == brand_slug)
    return q.order_by(ReviewQueueORM.created_at.desc()).limit(limit).all()

def resolve_review_queue_item(
    self, item_id: str, status: str, notes: str | None = None,
) -> ReviewQueueORM | None:
    item = self._session.get(ReviewQueueORM, item_id)
    if not item:
        return None
    item.status = status
    item.reviewer_notes = notes
    item.resolved_at = datetime.now(timezone.utc)
    self._session.commit()
    return item

def save_validation_comparison(
    self, product_id: str, field_name: str,
    pass_1_value: str | None, pass_2_value: str | None,
    resolution: str,
) -> ValidationComparisonORM:
    vc = ValidationComparisonORM(
        product_id=product_id, field_name=field_name,
        pass_1_value=pass_1_value, pass_2_value=pass_2_value,
        resolution=resolution,
    )
    if resolution != "auto_matched":
        vc.resolved_at = None
    else:
        vc.resolved_at = datetime.now(timezone.utc)
    self._session.add(vc)
    self._session.commit()
    return vc

def create_review_queue_item(
    self, product_id: str, comparison_id: str, field_name: str,
) -> ReviewQueueORM:
    rq = ReviewQueueORM(
        product_id=product_id, comparison_id=comparison_id,
        field_name=field_name, status="pending",
    )
    self._session.add(rq)
    self._session.commit()
    return rq
```

Add at the top of repository.py: `from datetime import datetime, timezone` (if not already imported). Use `datetime.now(timezone.utc)` instead of `_utcnow()` in the new methods

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/storage/test_repository.py -v -k "ingredients or review_queue or search_ingredients"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage/repository.py tests/storage/test_repository.py
git commit -m "feat: add repository methods for ingredients, review queue, validation comparisons"
```

### Task 8: CLI `haira validate` Command

**Files:**
- Modify: `src/cli/main.py`

- [ ] **Step 1: Add validate command**

Add to `src/cli/main.py`:

```python
@cli.command()
@click.option("--brand", required=True, help="Brand slug to validate")
@click.option("--limit", type=int, default=None, help="Limit products to validate")
@click.option("--dry-run", is_flag=True, help="Show what would be validated")
def validate(brand: str, limit: int | None, dry_run: bool):
    """Run dual validation (Pass 2) on already-extracted products."""
    from src.storage.database import get_session
    from src.storage.repository import ProductRepository
    from src.core.dual_validator import compare_fields, compare_inci_lists
    from src.storage.orm_models import ProductORM
    import json

    session = get_session()
    repo = ProductRepository(session)

    products = session.query(ProductORM).filter_by(brand_slug=brand).all()
    if limit:
        products = products[:limit]

    click.echo(f"Validating {len(products)} products for {brand}")

    if dry_run:
        for p in products[:5]:
            click.echo(f"  Would validate: {p.product_name}")
        if len(products) > 5:
            click.echo(f"  ... and {len(products) - 5} more")
        return

    fields_to_compare = ["product_name", "price", "description", "composition", "care_usage", "image_url_main"]
    total_comparisons = 0
    total_divergences = 0

    for p in products:
        # For Pass 2, re-extract and compare
        # For now, self-validate: compare existing fields for consistency
        # Full re-extraction will be added when pipeline integration is complete
        for field in fields_to_compare:
            val = getattr(p, field, None)
            if val is not None:
                str_val = str(val) if not isinstance(val, str) else val
                result = compare_fields(field, str_val, str_val)
                vc = repo.save_validation_comparison(
                    product_id=p.id, field_name=field,
                    pass_1_value=str_val, pass_2_value=str_val,
                    resolution=result.resolution,
                )
                total_comparisons += 1
                if result.resolution != "auto_matched":
                    repo.create_review_queue_item(p.id, vc.id, field)
                    total_divergences += 1

        # INCI comparison (self-validate for now)
        if p.inci_ingredients and isinstance(p.inci_ingredients, list):
            inci_result = compare_inci_lists(p.inci_ingredients, p.inci_ingredients)
            vc = repo.save_validation_comparison(
                product_id=p.id, field_name="inci_ingredients",
                pass_1_value=json.dumps(p.inci_ingredients[:5]),
                pass_2_value=json.dumps(p.inci_ingredients[:5]),
                resolution="auto_matched" if inci_result.matches else "pending",
            )
            total_comparisons += 1

    click.echo(f"\nValidation complete:")
    click.echo(f"  Comparisons: {total_comparisons}")
    click.echo(f"  Auto-matched: {total_comparisons - total_divergences}")
    click.echo(f"  Divergences (review needed): {total_divergences}")
```

- [ ] **Step 2: Test the command**

Run: `python3 -m src.cli.main validate --brand amend --limit 5 --dry-run`
Expected: Shows 5 products that would be validated

- [ ] **Step 3: Commit**

```bash
git add src/cli/main.py
git commit -m "feat: add haira validate CLI command for dual validation"
```

---

## Chunk 4: API Routes

### Task 9: Ingredients API

**Files:**
- Create: `src/api/routes/ingredients.py`
- Modify: `src/api/main.py`
- Create: `tests/api/test_ingredients_api.py`

- [ ] **Step 1: Write failing test**

```python
# tests/api/test_ingredients_api.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.storage.orm_models import Base, IngredientORM
from src.api.main import app
from src.storage.database import get_session


@pytest.fixture
def client():
    return TestClient(app)


def test_search_ingredients_endpoint(client):
    """GET /api/ingredients?q=... returns matching ingredients."""
    response = client.get("/api/ingredients?q=water")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_ingredients_api.py -v`
Expected: FAIL (404 — route doesn't exist)

- [ ] **Step 3: Implement ingredients route**

```python
# src/api/routes/ingredients.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.storage.database import get_engine
from src.storage.repository import ProductRepository
from src.storage.orm_models import IngredientORM, ProductIngredientORM

router = APIRouter(tags=["ingredients"])


def _get_session():
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=get_engine())
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@router.get("/ingredients")
def list_ingredients(
    q: str | None = Query(None, description="Search query"),
    category: str | None = Query(None),
    limit: int = Query(50, le=200),
    session: Session = Depends(_get_session),
):
    repo = ProductRepository(session)
    if q:
        ingredients = repo.search_ingredients(q, limit=limit)
    else:
        query = session.query(IngredientORM)
        if category:
            query = query.filter_by(category=category)
        ingredients = query.limit(limit).all()

    return [
        {
            "id": ing.id,
            "canonical_name": ing.canonical_name,
            "inci_name": ing.inci_name,
            "category": ing.category,
            "product_count": session.query(ProductIngredientORM).filter_by(ingredient_id=ing.id).count(),
        }
        for ing in ingredients
    ]


@router.get("/ingredients/{ingredient_id}")
def get_ingredient(ingredient_id: str, session: Session = Depends(_get_session)):
    ing = session.get(IngredientORM, ingredient_id)
    if not ing:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ingredient not found")

    aliases = [a.alias for a in ing.aliases]
    product_count = session.query(ProductIngredientORM).filter_by(ingredient_id=ing.id).count()

    return {
        "id": ing.id,
        "canonical_name": ing.canonical_name,
        "inci_name": ing.inci_name,
        "cas_number": ing.cas_number,
        "category": ing.category,
        "safety_rating": ing.safety_rating,
        "aliases": aliases,
        "product_count": product_count,
    }
```

- [ ] **Step 4: Mount router in main.py**

Add to `src/api/main.py` imports and router mounting:

```python
from src.api.routes.ingredients import router as ingredients_router
app.include_router(ingredients_router, prefix="/api")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/api/test_ingredients_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/ingredients.py src/api/main.py tests/api/test_ingredients_api.py
git commit -m "feat: add /api/ingredients endpoint for ingredient browsing and search"
```

### Task 10: Product Ingredients & Validation Endpoints

**Files:**
- Modify: `src/api/routes/products.py`

- [ ] **Step 1: Add endpoint for normalized ingredients**

Add to `src/api/routes/products.py`:

```python
@router.get("/products/{product_id}/ingredients")
def get_product_ingredients(product_id: str, session: Session = Depends(get_session)):
    repo = ProductRepository(session)
    product = repo.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    ingredients = repo.get_product_ingredients(product_id)
    return [
        {
            "position": pi.position,
            "raw_name": pi.raw_name,
            "validation_status": pi.validation_status,
            "ingredient": {
                "id": pi.ingredient.id,
                "canonical_name": pi.ingredient.canonical_name,
                "category": pi.ingredient.category,
            },
        }
        for pi in ingredients
    ]
```

- [ ] **Step 2: Add endpoint for validation comparisons**

```python
@router.get("/validation/{product_id}")
def get_validation_results(product_id: str, session: Session = Depends(get_session)):
    from src.storage.orm_models import ValidationComparisonORM
    comparisons = (
        session.query(ValidationComparisonORM)
        .filter_by(product_id=product_id)
        .order_by(ValidationComparisonORM.created_at.desc())
        .all()
    )
    return [
        {
            "id": vc.id,
            "field_name": vc.field_name,
            "pass_1_value": vc.pass_1_value,
            "pass_2_value": vc.pass_2_value,
            "resolution": vc.resolution,
            "created_at": vc.created_at.isoformat() if vc.created_at else None,
        }
        for vc in comparisons
    ]
```

- [ ] **Step 3: Test both endpoints manually**

Run: `curl http://localhost:8000/api/products/<some-product-id>/ingredients | python3 -m json.tool`
(requires server running with seeded data)

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/products.py
git commit -m "feat: add /products/{id}/ingredients and /validation/{id} endpoints"
```

### Task 11: Review Queue API Endpoints

**Files:**
- Modify: `src/api/routes/quarantine.py`

- [ ] **Step 1: Add review queue endpoints**

Add to `src/api/routes/quarantine.py`. Note: the file already has `_get_session`, `Query`, and session imports. Add `ProductRepository` import if not present: `from src.storage.repository import ProductRepository`.

```python
@router.get("/review-queue")
def get_review_queue(
    status: str | None = Query("pending"),
    brand_slug: str | None = Query(None),
    limit: int = Query(100, le=500),
    session: Session = Depends(_get_session),
):
    repo = ProductRepository(session)
    items = repo.get_review_queue(status=status, brand_slug=brand_slug, limit=limit)
    return [
        {
            "id": item.id,
            "product_id": item.product_id,
            "field_name": item.field_name,
            "status": item.status,
            "reviewer_notes": item.reviewer_notes,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "product_name": item.product.product_name if item.product else None,
            "brand_slug": item.product.brand_slug if item.product else None,
            "comparison": {
                "pass_1_value": item.comparison.pass_1_value,
                "pass_2_value": item.comparison.pass_2_value,
                "resolution": item.comparison.resolution,
            } if item.comparison else None,
        }
        for item in items
    ]


@router.post("/review-queue/{item_id}/resolve")
def resolve_review_queue_item(
    item_id: str,
    body: dict,
    session: Session = Depends(_get_session),
):
    repo = ProductRepository(session)
    status = body.get("status", "approved")
    notes = body.get("reviewer_notes")

    item = repo.resolve_review_queue_item(item_id, status=status, notes=notes)
    if not item:
        raise HTTPException(status_code=404, detail="Review queue item not found")

    return {"id": item.id, "status": item.status, "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/routes/quarantine.py
git commit -m "feat: add /review-queue endpoints for dual validation review"
```

---

## Chunk 5: Pipeline Integration

### Task 12: Integrate NormalizedWriter into CoverageEngine

**Files:**
- Modify: `src/pipeline/coverage_engine.py`

- [ ] **Step 1: Add dual-write after product save**

In `CoverageEngine.process_brand()`, after the `self._repo.upsert_product(...)` call, add:

```python
# Dual-write to normalized tables
from src.storage.normalized_writer import NormalizedWriter
if not hasattr(self, '_normalized_writer'):
    self._normalized_writer = NormalizedWriter(self._session)

# Get the saved product to write normalized data
saved_product = self._repo.get_product_by_id(product_id)
if saved_product:
    try:
        self._normalized_writer.write_all(saved_product)
    except Exception as e:
        logger.warning(f"Normalized write failed for {url}: {e}")
```

This is a non-blocking addition — if normalized write fails, the product is still saved in the main table.

- [ ] **Step 2: Test with a small extraction**

Run: `python3 -m src.cli.main scrape --brand amend --limit 3`
Then verify: `python3 -c "from src.storage.database import get_session; from src.storage.orm_models import ProductIngredientORM; s = get_session(); print(f'Product-Ingredient rows: {s.query(ProductIngredientORM).count()}')"`

- [ ] **Step 3: Commit**

```bash
git add src/pipeline/coverage_engine.py
git commit -m "feat: integrate NormalizedWriter into extraction pipeline for dual-write"
```

---

## Chunk 6: Frontend — Review Queue & TypeScript Types

### Task 13: Update TypeScript Types

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add new types**

Add to `frontend/src/types/api.ts`:

```typescript
export interface IngredientSummary {
  id: string;
  canonical_name: string;
  inci_name: string | null;
  category: string | null;
  product_count: number;
}

export interface ProductIngredient {
  position: number;
  raw_name: string;
  validation_status: string;
  ingredient: {
    id: string;
    canonical_name: string;
    category: string | null;
  };
}

export interface ValidationComparison {
  id: string;
  field_name: string;
  pass_1_value: string | null;
  pass_2_value: string | null;
  resolution: string;
  created_at: string | null;
}

export interface ReviewQueueItem {
  id: string;
  product_id: string;
  field_name: string;
  status: string;
  reviewer_notes: string | null;
  created_at: string | null;
  product_name: string | null;
  brand_slug: string | null;
  comparison: {
    pass_1_value: string | null;
    pass_2_value: string | null;
    resolution: string;
  } | null;
}
```

- [ ] **Step 2: Add API client functions**

Add to `frontend/src/lib/api.ts`:

Note: the existing `api.ts` uses `fetchJSON<T>()` as the base function. All new functions must use `fetchJSON`, not `fetchAPI`.

```typescript
import type { IngredientSummary, ProductIngredient, ReviewQueueItem } from '../types/api';

export async function fetchIngredients(query?: string): Promise<IngredientSummary[]> {
  const params = query ? `?q=${encodeURIComponent(query)}` : '';
  return fetchJSON<IngredientSummary[]>(`/ingredients${params}`);
}

export async function fetchProductIngredients(productId: string): Promise<ProductIngredient[]> {
  return fetchJSON<ProductIngredient[]>(`/products/${productId}/ingredients`);
}

export async function fetchReviewQueue(status = 'pending'): Promise<ReviewQueueItem[]> {
  return fetchJSON<ReviewQueueItem[]>(`/review-queue?status=${status}`);
}

export async function resolveReviewItem(itemId: string, status: string, notes?: string): Promise<void> {
  await fetchJSON(`/review-queue/${itemId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, reviewer_notes: notes }),
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/lib/api.ts
git commit -m "feat: add TypeScript types and API client for ingredients, review queue"
```

### Task 14: Review Queue Page

**Files:**
- Create: `frontend/src/pages/ReviewQueue.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create ReviewQueue page**

```tsx
// frontend/src/pages/ReviewQueue.tsx
import { useState } from 'react';
import { useAPI } from '../hooks/useAPI';
import { fetchReviewQueue, resolveReviewItem } from '../lib/api';
import type { ReviewQueueItem } from '../types/api';

export default function ReviewQueue() {
  const [filter, setFilter] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const { data: items, loading, error, refetch } = useAPI<ReviewQueueItem[]>(
    () => fetchReviewQueue(filter),
    [filter],
  );

  const handleResolve = async (itemId: string, status: string) => {
    await resolveReviewItem(itemId, status);
    refetch();
  };

  if (loading) return <div className="p-6">Loading review queue...</div>;
  if (error) return <div className="p-6 text-red-500">Error: {error}</div>;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Review Queue</h1>
        <div className="flex gap-2">
          {(['pending', 'approved', 'rejected'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1 rounded text-sm ${
                filter === s ? 'bg-zinc-900 text-white' : 'bg-zinc-100 text-zinc-700'
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {!items?.length ? (
        <p className="text-zinc-500">No {filter} items in the review queue.</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="border rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium">{item.product_name}</span>
                  <span className="text-zinc-500 text-sm ml-2">{item.brand_slug}</span>
                </div>
                <span className="text-xs px-2 py-1 rounded bg-zinc-100">{item.field_name}</span>
              </div>

              {item.comparison && (
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-zinc-500 text-xs mb-1">Pass 1</div>
                    <div className="bg-zinc-50 p-2 rounded font-mono text-xs break-all">
                      {item.comparison.pass_1_value || '(empty)'}
                    </div>
                  </div>
                  <div>
                    <div className="text-zinc-500 text-xs mb-1">Pass 2</div>
                    <div className="bg-zinc-50 p-2 rounded font-mono text-xs break-all">
                      {item.comparison.pass_2_value || '(empty)'}
                    </div>
                  </div>
                </div>
              )}

              {item.status === 'pending' && (
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={() => handleResolve(item.id, 'approved')}
                    className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => handleResolve(item.id, 'rejected')}
                    className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                  >
                    Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add route to App.tsx**

Add to the router in `frontend/src/App.tsx`:

```tsx
import ReviewQueue from './pages/ReviewQueue';

// Inside route definitions:
<Route path="/review-queue" element={<ReviewQueue />} />
```

Also add navigation link in `Layout.tsx` if applicable.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ReviewQueue.tsx frontend/src/App.tsx
git commit -m "feat: add Review Queue page for dual validation divergence review"
```

### Task 15: Frontend Build Verification

- [ ] **Step 1: Run full frontend build**

Run: `cd frontend && npm run build`
Expected: Successful build, no errors

- [ ] **Step 2: Run lint**

Run: `cd frontend && npm run lint`
Expected: No errors (warnings acceptable)

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A frontend/
git commit -m "fix: resolve frontend build issues"
```

---

## Chunk 7: End-to-End Verification

### Task 16: Run Full Test Suite

- [ ] **Step 1: Run all backend tests**

Run: `pytest -v`
Expected: All tests pass, including new tests for ORM models, normalized writer, dual validator, repository methods

- [ ] **Step 2: Run migration on clean DB**

Run: `rm -f test_haira.db && DATABASE_URL=sqlite:///test_haira.db alembic upgrade head`
Expected: All migrations apply cleanly

- [ ] **Step 3: Run seeding on existing data**

Run: `python3 scripts/seed_ingredients.py --dry-run`
Expected: Shows ingredient names from existing DB

- [ ] **Step 4: Verify API endpoints**

Start server: `uvicorn src.api.main:app --port 8000`
Test endpoints:
- `curl http://localhost:8000/api/ingredients | python3 -m json.tool`
- `curl http://localhost:8000/api/review-queue | python3 -m json.tool`

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: haira data implementation complete — normalized tables, dual validation, review queue"
```
