"""
database/models.py
──────────────────
SQLAlchemy ORM models — each class = one database table.

Beginner tip: Think of each class as a spreadsheet table.
  - Each attribute = a column in that table.
  - SQLAlchemy handles creating the table & writing SQL for us.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text,
    DateTime, Boolean, ForeignKey, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship


# Every model must inherit from this Base class
class Base(DeclarativeBase):
    pass


class Site(Base):
    """Stores the websites we've registered / analyzed."""
    __tablename__ = "sites"

    id          = Column(Integer, primary_key=True, index=True)
    url         = Column(String(500), unique=True, nullable=False, index=True)
    name        = Column(String(200), nullable=True)       # Optional friendly name
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # One site → many reports (SQLAlchemy handles the JOIN for us)
    seo_reports           = relationship("SEOReport",           back_populates="site", cascade="all, delete-orphan")
    accessibility_reports = relationship("AccessibilityReport", back_populates="site", cascade="all, delete-orphan")
    content_reports       = relationship("ContentReport",       back_populates="site", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Site id={self.id} url={self.url}>"


class SEOReport(Base):
    """Stores one SEO analysis snapshot for a site."""
    __tablename__ = "seo_reports"

    id                  = Column(Integer, primary_key=True, index=True)
    site_id             = Column(Integer, ForeignKey("sites.id"), nullable=False)
    overall_score       = Column(Float, default=0.0)   # 0–100

    # Title & description
    title               = Column(String(500), nullable=True)
    title_length        = Column(Integer, default=0)
    title_ok            = Column(Boolean, default=False)
    meta_description    = Column(Text, nullable=True)
    meta_desc_length    = Column(Integer, default=0)
    meta_desc_ok        = Column(Boolean, default=False)

    # Headers
    h1_count            = Column(Integer, default=0)
    h2_count            = Column(Integer, default=0)
    h3_count            = Column(Integer, default=0)
    header_hierarchy_ok = Column(Boolean, default=False)

    # Images
    total_images        = Column(Integer, default=0)
    images_missing_alt  = Column(Integer, default=0)
    alt_coverage_pct    = Column(Float, default=0.0)

    # Technical
    has_sitemap         = Column(Boolean, default=False)
    has_robots_txt      = Column(Boolean, default=False)
    page_size_kb        = Column(Float, default=0.0)

    # Raw details stored as JSON (flexible)
    details             = Column(JSON, nullable=True)

    created_at          = Column(DateTime, default=datetime.utcnow)
    site                = relationship("Site", back_populates="seo_reports")

    def __repr__(self):
        return f"<SEOReport id={self.id} site_id={self.site_id} score={self.overall_score}>"


class AccessibilityReport(Base):
    """Stores one accessibility analysis snapshot for a site."""
    __tablename__ = "accessibility_reports"

    id                   = Column(Integer, primary_key=True, index=True)
    site_id              = Column(Integer, ForeignKey("sites.id"), nullable=False)
    overall_score        = Column(Float, default=0.0)

    # Images
    images_missing_alt   = Column(Integer, default=0)

    # ARIA
    aria_labels_count    = Column(Integer, default=0)
    missing_aria_labels  = Column(Integer, default=0)

    # Forms
    total_form_inputs    = Column(Integer, default=0)
    inputs_missing_label = Column(Integer, default=0)

    # Semantic HTML
    has_main_landmark    = Column(Boolean, default=False)
    has_nav_landmark     = Column(Boolean, default=False)
    has_header_landmark  = Column(Boolean, default=False)
    has_footer_landmark  = Column(Boolean, default=False)

    # Color contrast (heuristic only)
    contrast_issues      = Column(Integer, default=0)

    details              = Column(JSON, nullable=True)
    created_at           = Column(DateTime, default=datetime.utcnow)
    site                 = relationship("Site", back_populates="accessibility_reports")


class ContentReport(Base):
    """Stores one content quality analysis snapshot for a site."""
    __tablename__ = "content_reports"

    id                       = Column(Integer, primary_key=True, index=True)
    site_id                  = Column(Integer, ForeignKey("sites.id"), nullable=False)
    overall_score            = Column(Float, default=0.0)

    word_count               = Column(Integer, default=0)
    readability_score        = Column(Float, default=0.0)   # Flesch reading ease
    readability_grade        = Column(String(50), nullable=True)
    broken_links_count       = Column(Integer, default=0)
    internal_links_count     = Column(Integer, default=0)
    external_links_count     = Column(Integer, default=0)
    duplicate_content_flag   = Column(Boolean, default=False)
    duplicate_content_reason = Column(Text, nullable=True)

    details                  = Column(JSON, nullable=True)
    created_at               = Column(DateTime, default=datetime.utcnow)
    site                     = relationship("Site", back_populates="content_reports")


class DBOperationLog(Base):
    """Audit log — every INSERT/UPDATE/DELETE the agent performs is recorded here."""
    __tablename__ = "db_operation_logs"

    id             = Column(Integer, primary_key=True, index=True)
    operation      = Column(String(10), nullable=False)   # SELECT / INSERT / UPDATE / DELETE
    table_name     = Column(String(100), nullable=False)
    query_summary  = Column(Text, nullable=True)          # Human-readable description
    parameters     = Column(JSON, nullable=True)          # What values were used
    success        = Column(Boolean, default=True)
    error_message  = Column(Text, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)