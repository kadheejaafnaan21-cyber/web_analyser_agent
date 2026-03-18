"""
config/settings.py
──────────────────
Central configuration for the entire application.
All environment variables and constants live here.
"""

import os
from dotenv import load_dotenv

# Load variables from .env file into the environment
load_dotenv()


# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./seo_agent.db")

# ── Request Settings ──────────────────────────────────────────────────────────
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "15"))

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

# ── LLM Model ─────────────────────────────────────────────────────────────────
# Using Claude claude-sonnet-4-20250514 — good balance of speed and intelligence
MODEL_NAME: str = "claude-sonnet-4-20250514"
MAX_TOKENS: int = 4096

# ── Database Safety ───────────────────────────────────────────────────────────
# ONLY these tables may be touched by the agent — anything else is blocked
ALLOWED_TABLES: list[str] = [
    "sites",            # Stores registered websites
    "seo_reports",      # SEO analysis results
    "accessibility_reports",  # Accessibility analysis results
    "content_reports",  # Content quality results
    "db_operation_logs", # Audit log for all DB operations
]

# ── SEO Thresholds ────────────────────────────────────────────────────────────
SEO_SCORE_LOW_THRESHOLD: int = 50      # Below this = "low SEO score"
SEO_TITLE_MIN_LENGTH: int = 30
SEO_TITLE_MAX_LENGTH: int = 60
SEO_DESC_MIN_LENGTH: int = 120
SEO_DESC_MAX_LENGTH: int = 160

# ── Content Thresholds ────────────────────────────────────────────────────────
MIN_WORD_COUNT: int = 300              # Minimum recommended words per page
READABILITY_GOOD_THRESHOLD: float = 60.0  # Flesch reading ease score