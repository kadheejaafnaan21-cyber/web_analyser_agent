"""
tests/test_database.py
───────────────────────
Tests for database operations and safety guards.
Uses an in-memory SQLite database so tests don't touch the real DB.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from database.models import Base, Site, SEOReport
from database.db_operations import (
    get_or_create_site,
    save_seo_report,
    get_seo_reports,
    get_low_seo_sites,
    update_seo_score,
    delete_old_reports,
    _assert_allowed_table,
)


class TestSafetyGuards:
    """Ensure the table whitelist works correctly."""

    def test_allowed_table_passes(self):
        # Should not raise
        _assert_allowed_table("sites")
        _assert_allowed_table("seo_reports")

    def test_forbidden_table_raises(self):
        with pytest.raises(PermissionError):
            _assert_allowed_table("users")

    def test_sql_injection_attempt_blocked(self):
        with pytest.raises(PermissionError):
            _assert_allowed_table("sites; DROP TABLE sites;--")


class TestDatabaseOperations:
    """Integration tests using an in-memory SQLite database."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Create a fresh in-memory DB for each test."""
        # Create an in-memory engine (disappears after test)
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine)

        # Patch get_db to use our test session
        from contextlib import contextmanager

        @contextmanager
        def mock_get_db():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("database.db_operations.get_db", mock_get_db):
            yield

    def test_create_site(self):
        site = get_or_create_site("https://testsite.com", "Test Site")
        assert site["url"] == "https://testsite.com"
        assert site["id"] is not None

    def test_get_or_create_idempotent(self):
        """Calling twice should return the same site, not create two."""
        site1 = get_or_create_site("https://duplicate.com")
        site2 = get_or_create_site("https://duplicate.com")
        assert site1["id"] == site2["id"]

    def test_save_and_retrieve_seo_report(self):
        site = get_or_create_site("https://seotest.com")
        report_data = {
            "overall_score": 75.5,
            "title": "Test Title",
            "title_length": 10,
            "title_ok": True,
            "h1_count": 1,
            "images_missing_alt": 0,
        }
        saved = save_seo_report(site["id"], report_data)
        assert saved["overall_score"] == 75.5

        reports = get_seo_reports(site["id"])
        assert len(reports) == 1
        assert reports[0]["overall_score"] == 75.5

    def test_update_seo_score(self):
        site = get_or_create_site("https://updatetest.com")
        saved = save_seo_report(site["id"], {"overall_score": 40.0})
        result = update_seo_score(saved["id"], 90.0)
        assert result["new_score"] == 90.0
        assert result["old_score"] == 40.0