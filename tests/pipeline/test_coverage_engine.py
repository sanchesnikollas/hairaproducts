# tests/pipeline/test_coverage_engine.py
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.orm_models import Base
from src.pipeline.coverage_engine import CoverageEngine
from src.pipeline.report_generator import BrandReport, generate_coverage_stats


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class TestBrandReport:
    def test_initial_state(self):
        report = BrandReport(brand_slug="test")
        assert report.verified_inci_rate == 0.0
        assert report.failure_rate == 0.0

    def test_verified_rate(self):
        report = BrandReport(brand_slug="test", extracted_total=10, verified_inci_total=7)
        assert report.verified_inci_rate == 0.7

    def test_failure_rate(self):
        report = BrandReport(brand_slug="test", extracted_total=10, quarantined_total=3)
        assert report.failure_rate == 0.3

    def test_to_dict(self):
        report = BrandReport(brand_slug="test", extracted_total=5, verified_inci_total=3)
        d = report.to_dict()
        assert d["brand_slug"] == "test"
        assert d["verified_inci_rate"] == 0.6

    def test_complete(self):
        report = BrandReport(brand_slug="test")
        assert report.completed_at is None
        report.complete()
        assert report.completed_at is not None


class TestGenerateCoverageStats:
    def test_generates_stats_dict(self):
        report = BrandReport(
            brand_slug="amend",
            discovered_total=100,
            hair_total=80,
            kits_total=5,
            non_hair_total=15,
            extracted_total=80,
            verified_inci_total=60,
            catalog_only_total=15,
            quarantined_total=5,
        )
        stats = generate_coverage_stats(report)
        assert stats["brand_slug"] == "amend"
        assert stats["verified_inci_rate"] == 0.75
        assert stats["status"] == "done"


class TestCoverageEngine:
    def test_process_brand_no_browser(self, db_session):
        engine = CoverageEngine(session=db_session, browser=None)
        blueprint = {
            "brand_slug": "test",
            "allowed_domains": ["www.test.com"],
            "entrypoints": [],
            "extraction": {
                "inci_selectors": [],
                "name_selectors": [],
            },
        }
        urls = [
            {"url": "https://www.test.com/shampoo-gold-black-reparador"},
            {"url": "https://www.test.com/kit-combo"},
            {"url": "https://www.test.com/corpo/hidratante-corporal"},
        ]
        report = engine.process_brand("test", blueprint, urls)
        assert report.brand_slug == "test"
        assert report.discovered_total == 3
        assert report.completed_at is not None

    def test_stop_the_line(self, db_session):
        mock_browser = MagicMock()
        # Return HTML with no product name to trigger failures
        mock_browser.fetch_page.return_value = "<html><body>Empty page</body></html>"

        engine = CoverageEngine(session=db_session, browser=mock_browser)
        blueprint = {
            "brand_slug": "test",
            "allowed_domains": ["www.test.com"],
            "entrypoints": [],
            "extraction": {
                "inci_selectors": [],
                "name_selectors": [],
            },
        }
        # All product-like URLs, but extraction returns empty so they get skipped
        urls = [{"url": f"https://www.test.com/produto-{i}-reparador"} for i in range(10)]
        report = engine.process_brand("test", blueprint, urls)
        assert report.discovered_total == 10
