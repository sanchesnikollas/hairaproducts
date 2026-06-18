"""_fetch_alternatives must consume the GOLD tier first, falling back to the
legacy verified_inci pool only until the Gold backfill has run in production."""
import os
import tempfile

import pytest


@pytest.fixture()
def seeded_session():
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.NamedTemporaryFile(suffix='.db', delete=False).name}"
    from src.storage import database as dbmod
    dbmod.reset_engine()
    from sqlalchemy import text
    from sqlalchemy.orm import Session as SASession
    from src.storage.orm_models import Base, ProductORM, IngredientORM

    engine = dbmod.get_engine()
    Base.metadata.create_all(engine)
    inci = ["Sodium Laureth Sulfate", "Cocamidopropyl Betaine", "Glycerin"]
    with SASession(engine) as s:
        # category index + compatibility rules so _score_fast yields matched>=2
        s.add_all([
            IngredientORM(canonical_name="Sodium Laureth Sulfate", category="surfactant"),
            IngredientORM(canonical_name="Cocamidopropyl Betaine", category="surfactant"),
            IngredientORM(canonical_name="Glycerin", category="humectant"),
        ])
        s.execute(text("CREATE TABLE IF NOT EXISTS ingredient_category_compatibility "
                       "(category TEXT, hair_type TEXT, score INTEGER)"))
        s.execute(text("INSERT INTO ingredient_category_compatibility VALUES "
                       "('surfactant','cacheado',1),('humectant','cacheado',1)"))
        s.add_all([
            ProductORM(brand_slug="acme", product_name="Shampoo Gold 300ml", product_url="u/gold",
                       verification_status="verified_inci", gold_status="gold",
                       product_type_normalized="shampoo", inci_ingredients=inci),
            ProductORM(brand_slug="acme", product_name="Shampoo Catalog 300ml", product_url="u/cat",
                       verification_status="verified_inci", gold_status="catalog",
                       product_type_normalized="shampoo", inci_ingredients=inci),
        ])
        s.commit()
    return engine, SASession


def _fetch(engine, SASession):
    import src.api.routes.moon as moon
    moon._CAT_INDEX = None
    moon._RULES_INDEX = None
    with SASession(engine) as s:
        return moon._fetch_alternatives(s, ["cacheado"], "shampoo", None)


def test_gold_tier_preferred(seeded_session):
    engine, SASession = seeded_session
    results = _fetch(engine, SASession)
    ids = {r["product_id"] for r in results}
    with SASession(engine) as s:
        from src.storage.orm_models import ProductORM
        gold_id = s.query(ProductORM).filter_by(product_url="u/gold").one().id
        cat_id = s.query(ProductORM).filter_by(product_url="u/cat").one().id
    assert gold_id in ids
    assert cat_id not in ids  # catalog tier must NOT be recommended while Gold exists


def test_fallback_to_verified_when_no_gold(seeded_session):
    engine, SASession = seeded_session
    from src.storage.orm_models import ProductORM
    with SASession(engine) as s:
        s.query(ProductORM).filter_by(product_url="u/gold").one().gold_status = "catalog"
        s.commit()
    results = _fetch(engine, SASession)
    assert results, "fallback should still return verified_inci products when no Gold exists"
