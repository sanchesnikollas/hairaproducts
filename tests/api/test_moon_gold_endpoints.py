"""GET /moon/gold (browse the Gold pool) and GET /moon/gold/{id} (full contract)."""
import os
import tempfile

import pytest
from fastapi import HTTPException

GOOD = ["Aqua", "Sodium Laureth Sulfate", "Glycerin", "Parfum", "Limonene"]


@pytest.fixture()
def session_with_gold():
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.NamedTemporaryFile(suffix='.db', delete=False).name}"
    from src.storage import database as dbmod
    dbmod.reset_engine()
    from sqlalchemy.orm import Session as SASession
    from src.storage.orm_models import Base, ProductORM

    engine = dbmod.get_engine()
    Base.metadata.create_all(engine)
    with SASession(engine) as s:
        s.add(ProductORM(
            brand_slug="acme", product_name="Shampoo Gold 300ml", product_url="u/g",
            gold_status="gold", verification_status="verified_inci", product_category="shampoo",
            function_objective="limpar", hair_type=["cacheado", "seco"], inci_ingredients=GOOD,
            usage_instructions="Aplique e enxágue.",
            description="Shampoo de limpeza suave para uso diário em cabelos oleosos.",
            image_url_main="https://a.com/i.jpg",
        ))
        s.add(ProductORM(
            brand_slug="acme", product_name="Shampoo Catalog", product_url="u/c",
            gold_status="catalog", verification_status="verified_inci", product_category="shampoo",
        ))
        s.commit()
    return engine, SASession


def _ids(engine, SASession):
    from src.storage.orm_models import ProductORM
    with SASession(engine) as s:
        g = s.query(ProductORM).filter_by(product_url="u/g").one().id
        c = s.query(ProductORM).filter_by(product_url="u/c").one().id
    return g, c


def test_gold_product_returns_full_contract(session_with_gold):
    from src.api.routes.moon import gold_product
    engine, SASession = session_with_gold
    gid, _ = _ids(engine, SASession)
    with SASession(engine) as s:
        c = gold_product(gid, user={}, session=s)
    assert c["product_id"] == gid
    assert "cronograma_role" in c and "allergens" in c
    assert c["cronograma_role"]["cleansing_strength"] == "intensa"
    assert c["allergens"]["count"] >= 1


def test_gold_product_409_when_not_gold(session_with_gold):
    from src.api.routes.moon import gold_product
    engine, SASession = session_with_gold
    _, cid = _ids(engine, SASession)
    with SASession(engine) as s:
        with pytest.raises(HTTPException) as ei:
            gold_product(cid, user={}, session=s)
    assert ei.value.status_code == 409
    assert ei.value.detail["code"] == "NOT_GOLD"


def test_gold_list_filters(session_with_gold):
    from src.api.routes.moon import gold_list
    engine, SASession = session_with_gold
    gid, _ = _ids(engine, SASession)
    with SASession(engine) as s:
        hit = gold_list(hair_type="cacheado", function_objective="limpar", session=s, user={})
        assert hit["total"] == 1 and hit["items"][0]["product_id"] == gid
        miss = gold_list(hair_type="liso", session=s, user={})
        assert miss["total"] == 0  # catalog product never appears; gold one filtered out
