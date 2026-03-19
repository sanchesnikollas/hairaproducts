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
        alias = IngredientAliasORM(ingredient_id=ing.id, alias="DIMETHICONE", language="en")
        session.add(alias)
        session.commit()
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
        writer.write_product_ingredients(sample_product)
        rows = session.query(ProductIngredientORM).filter_by(product_id=sample_product.id).all()
        assert len(rows) == 3

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

    def test_write_product_claims(self, session, sample_product):
        from src.storage.normalized_writer import NormalizedWriter
        from src.storage.orm_models import ProductClaimORM, ClaimORM
        sample_product.product_labels = {"detected": ["sulfate_free"], "inferred": ["silicone_free"], "confidence": 0.9}
        session.commit()
        writer = NormalizedWriter(session)
        count = writer.write_product_claims(sample_product)
        assert count == 2
        assert session.query(ClaimORM).count() == 2
        assert session.query(ProductClaimORM).filter_by(product_id=sample_product.id).count() == 2

    def test_write_product_claims_skips_no_labels(self, session, sample_product):
        from src.storage.normalized_writer import NormalizedWriter
        writer = NormalizedWriter(session)
        count = writer.write_product_claims(sample_product)
        assert count == 0

    def test_write_product_images(self, session, sample_product):
        from src.storage.normalized_writer import NormalizedWriter
        from src.storage.orm_models import ProductImageORM
        sample_product.image_url_main = "https://example.com/main.jpg"
        sample_product.image_urls_gallery = ["https://example.com/1.jpg", "https://example.com/2.jpg"]
        session.commit()
        writer = NormalizedWriter(session)
        count = writer.write_product_images(sample_product)
        assert count == 3  # 1 main + 2 gallery
        rows = session.query(ProductImageORM).filter_by(product_id=sample_product.id).all()
        main = [r for r in rows if r.image_type == "main"]
        assert len(main) == 1

    def test_write_product_compositions(self, session, sample_product):
        from src.storage.normalized_writer import NormalizedWriter
        from src.storage.orm_models import ProductCompositionORM
        sample_product.composition = "Water, Glycerin, Fragrance"
        session.commit()
        writer = NormalizedWriter(session)
        count = writer.write_product_compositions(sample_product)
        assert count == 1
        row = session.query(ProductCompositionORM).filter_by(product_id=sample_product.id).first()
        assert row.content == "Water, Glycerin, Fragrance"

    def test_write_all(self, session, sample_product):
        from src.storage.normalized_writer import NormalizedWriter
        sample_product.image_url_main = "https://example.com/img.jpg"
        sample_product.product_labels = {"detected": ["vegan"], "inferred": [], "confidence": 0.8}
        session.commit()
        writer = NormalizedWriter(session)
        result = writer.write_all(sample_product)
        assert result["ingredients"] == 3
        assert result["claims"] == 1
        assert result["images"] == 1
        assert result["compositions"] == 0
