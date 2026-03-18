"""
database/db_operations.py
─────────────────────────
Safe, validated database operations.

KEY SAFETY RULES (read this!):
  1. Only ALLOWED_TABLES (from config) can be accessed — everything else raises an error.
  2. We NEVER execute raw user-typed SQL — we build queries using SQLAlchemy ORM
     which automatically prevents SQL injection attacks.
  3. Every operation is logged to db_operation_logs for auditing.
  4. Sessions auto-rollback on any error (see connection.py).
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from config.settings import ALLOWED_TABLES, SEO_SCORE_LOW_THRESHOLD
from database.models import (
    Site, SEOReport, AccessibilityReport,
    ContentReport, DBOperationLog
)
from database.connection import get_db
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Table name → ORM model mapping ───────────────────────────────────────────
TABLE_MODEL_MAP = {
    "sites":                  Site,
    "seo_reports":            SEOReport,
    "accessibility_reports":  AccessibilityReport,
    "content_reports":        ContentReport,
    "db_operation_logs":      DBOperationLog,
}


# ── Safety guard ─────────────────────────────────────────────────────────────

def _assert_allowed_table(table_name: str) -> None:
    """Raise immediately if the requested table is not whitelisted."""
    if table_name not in ALLOWED_TABLES:
        raise PermissionError(
            f"❌ Table '{table_name}' is not in the allowed list. "
            f"Allowed: {ALLOWED_TABLES}"
        )


# ── Audit logging ─────────────────────────────────────────────────────────────

def _log_operation(
    db: Session,
    operation: str,
    table_name: str,
    query_summary: str,
    parameters: dict | None = None,
    success: bool = True,
    error_message: str | None = None,
) -> None:
    """Write an entry to db_operation_logs (called after every DB action)."""
    log_entry = DBOperationLog(
        operation=operation,
        table_name=table_name,
        query_summary=query_summary,
        parameters=parameters,
        success=success,
        error_message=error_message,
    )
    db.add(log_entry)
    # Note: we DON'T commit here — the caller's session commit handles it


# ══════════════════════════════════════════════════════════════════════════════
# SITE operations
# ══════════════════════════════════════════════════════════════════════════════

def get_or_create_site(url: str, name: str | None = None) -> dict:
    """
    Return an existing site record or create a new one.
    Returns a plain dict so the LangGraph agent can easily read it.
    """
    _assert_allowed_table("sites")
    with get_db() as db:
        site = db.query(Site).filter(Site.url == url).first()
        if site is None:
            site = Site(url=url, name=name or url)
            db.add(site)
            db.flush()  # Assign an ID without committing yet
            _log_operation(db, "INSERT", "sites",
                           f"Created site: {url}", {"url": url, "name": name})
            logger.info(f"Created new site record: {url}")
        else:
            _log_operation(db, "SELECT", "sites",
                           f"Fetched existing site: {url}")
        return {"id": site.id, "url": site.url, "name": site.name}


def list_sites() -> list[dict]:
    """Return all registered sites."""
    _assert_allowed_table("sites")
    with get_db() as db:
        sites = db.query(Site).all()
        _log_operation(db, "SELECT", "sites", "Listed all sites")
        return [{"id": s.id, "url": s.url, "name": s.name,
                 "created_at": str(s.created_at)} for s in sites]


# ══════════════════════════════════════════════════════════════════════════════
# SEO REPORT operations
# ══════════════════════════════════════════════════════════════════════════════

def save_seo_report(site_id: int, data: dict) -> dict:
    """Insert a new SEO report row for the given site."""
    _assert_allowed_table("seo_reports")
    with get_db() as db:
        report = SEOReport(
            site_id=site_id,
            overall_score=data.get("overall_score", 0.0),
            title=data.get("title"),
            title_length=data.get("title_length", 0),
            title_ok=data.get("title_ok", False),
            meta_description=data.get("meta_description"),
            meta_desc_length=data.get("meta_desc_length", 0),
            meta_desc_ok=data.get("meta_desc_ok", False),
            h1_count=data.get("h1_count", 0),
            h2_count=data.get("h2_count", 0),
            h3_count=data.get("h3_count", 0),
            header_hierarchy_ok=data.get("header_hierarchy_ok", False),
            total_images=data.get("total_images", 0),
            images_missing_alt=data.get("images_missing_alt", 0),
            alt_coverage_pct=data.get("alt_coverage_pct", 0.0),
            has_sitemap=data.get("has_sitemap", False),
            has_robots_txt=data.get("has_robots_txt", False),
            page_size_kb=data.get("page_size_kb", 0.0),
            details=data.get("details"),
        )
        db.add(report)
        db.flush()
        _log_operation(db, "INSERT", "seo_reports",
                       f"Saved SEO report for site_id={site_id}",
                       {"site_id": site_id, "score": data.get("overall_score")})
        logger.info(f"SEO report saved: site_id={site_id}, score={data.get('overall_score')}")
        return {"id": report.id, "site_id": site_id,
                "overall_score": report.overall_score}


def get_seo_reports(site_id: int | None = None) -> list[dict]:
    """Fetch SEO reports, optionally filtered by site."""
    _assert_allowed_table("seo_reports")
    with get_db() as db:
        q = db.query(SEOReport)
        if site_id:
            q = q.filter(SEOReport.site_id == site_id)
        reports = q.order_by(SEOReport.created_at.desc()).all()
        _log_operation(db, "SELECT", "seo_reports",
                       f"Fetched SEO reports (site_id={site_id})")
        return [
            {
                "id": r.id, "site_id": r.site_id,
                "overall_score": r.overall_score,
                "title": r.title, "h1_count": r.h1_count,
                "images_missing_alt": r.images_missing_alt,
                "created_at": str(r.created_at),
            }
            for r in reports
        ]


def get_low_seo_sites() -> list[dict]:
    """Return all sites whose latest SEO score is below the threshold."""
    _assert_allowed_table("seo_reports")
    with get_db() as db:
        results = (
            db.query(SEOReport, Site)
            .join(Site, SEOReport.site_id == Site.id)
            .filter(SEOReport.overall_score < SEO_SCORE_LOW_THRESHOLD)
            .order_by(SEOReport.overall_score.asc())
            .all()
        )
        _log_operation(db, "SELECT", "seo_reports",
                       f"Queried sites with SEO score < {SEO_SCORE_LOW_THRESHOLD}")
        return [
            {"site_id": r.site_id, "url": s.url,
             "score": r.overall_score, "created_at": str(r.created_at)}
            for r, s in results
        ]


def update_seo_score(report_id: int, new_score: float) -> dict:
    """Update the overall_score field of a specific SEO report."""
    _assert_allowed_table("seo_reports")
    with get_db() as db:
        report = db.query(SEOReport).filter(SEOReport.id == report_id).first()
        if not report:
            raise ValueError(f"SEO report id={report_id} not found.")
        old_score = report.overall_score
        report.overall_score = new_score
        _log_operation(db, "UPDATE", "seo_reports",
                       f"Updated score report_id={report_id}: {old_score} → {new_score}",
                       {"report_id": report_id, "new_score": new_score})
        return {"id": report_id, "old_score": old_score, "new_score": new_score}


# ══════════════════════════════════════════════════════════════════════════════
# ACCESSIBILITY REPORT operations
# ══════════════════════════════════════════════════════════════════════════════

def save_accessibility_report(site_id: int, data: dict) -> dict:
    """Insert a new accessibility report."""
    _assert_allowed_table("accessibility_reports")
    with get_db() as db:
        report = AccessibilityReport(
            site_id=site_id,
            overall_score=data.get("overall_score", 0.0),
            images_missing_alt=data.get("images_missing_alt", 0),
            aria_labels_count=data.get("aria_labels_count", 0),
            missing_aria_labels=data.get("missing_aria_labels", 0),
            total_form_inputs=data.get("total_form_inputs", 0),
            inputs_missing_label=data.get("inputs_missing_label", 0),
            has_main_landmark=data.get("has_main_landmark", False),
            has_nav_landmark=data.get("has_nav_landmark", False),
            has_header_landmark=data.get("has_header_landmark", False),
            has_footer_landmark=data.get("has_footer_landmark", False),
            contrast_issues=data.get("contrast_issues", 0),
            details=data.get("details"),
        )
        db.add(report)
        db.flush()
        _log_operation(db, "INSERT", "accessibility_reports",
                       f"Saved accessibility report for site_id={site_id}",
                       {"site_id": site_id, "score": data.get("overall_score")})
        return {"id": report.id, "site_id": site_id,
                "overall_score": report.overall_score}


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT REPORT operations
# ══════════════════════════════════════════════════════════════════════════════

def save_content_report(site_id: int, data: dict) -> dict:
    """Insert a new content quality report."""
    _assert_allowed_table("content_reports")
    with get_db() as db:
        report = ContentReport(
            site_id=site_id,
            overall_score=data.get("overall_score", 0.0),
            word_count=data.get("word_count", 0),
            readability_score=data.get("readability_score", 0.0),
            readability_grade=data.get("readability_grade"),
            broken_links_count=data.get("broken_links_count", 0),
            internal_links_count=data.get("internal_links_count", 0),
            external_links_count=data.get("external_links_count", 0),
            duplicate_content_flag=data.get("duplicate_content_flag", False),
            duplicate_content_reason=data.get("duplicate_content_reason"),
            details=data.get("details"),
        )
        db.add(report)
        db.flush()
        _log_operation(db, "INSERT", "content_reports",
                       f"Saved content report for site_id={site_id}",
                       {"site_id": site_id, "score": data.get("overall_score")})
        return {"id": report.id, "site_id": site_id,
                "overall_score": report.overall_score}


# ══════════════════════════════════════════════════════════════════════════════
# DELETE operations
# ══════════════════════════════════════════════════════════════════════════════

def delete_old_reports(days: int = 30) -> dict:
    """
    Delete all report rows older than `days` days.
    This is the only bulk-delete we allow — targeted, not open-ended.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted_counts = {}

    report_models = [
        ("seo_reports", SEOReport),
        ("accessibility_reports", AccessibilityReport),
        ("content_reports", ContentReport),
    ]

    with get_db() as db:
        for table_name, model in report_models:
            _assert_allowed_table(table_name)
            count = db.query(model).filter(model.created_at < cutoff).count()
            db.query(model).filter(model.created_at < cutoff).delete()
            deleted_counts[table_name] = count
            _log_operation(db, "DELETE", table_name,
                           f"Deleted reports older than {days} days (cutoff={cutoff})",
                           {"days": days, "count": count})

    logger.info(f"Deleted old reports: {deleted_counts}")
    return {"deleted": deleted_counts, "cutoff_date": str(cutoff)}


# ══════════════════════════════════════════════════════════════════════════════
# QUERY LOG operations
# ══════════════════════════════════════════════════════════════════════════════

def get_operation_logs(limit: int = 50) -> list[dict]:
    """Fetch recent audit log entries."""
    _assert_allowed_table("db_operation_logs")
    with get_db() as db:
        logs = (
            db.query(DBOperationLog)
            .order_by(DBOperationLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": log.id,
                "operation": log.operation,
                "table": log.table_name,
                "summary": log.query_summary,
                "success": log.success,
                "created_at": str(log.created_at),
            }
            for log in logs
        ]