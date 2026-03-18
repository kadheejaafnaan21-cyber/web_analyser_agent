"""
database/connection.py
──────────────────────
Database engine setup and session management.

Beginner tip:
  - "Engine" = the connection to the database file/server.
  - "Session" = a single conversation with the DB (like opening a spreadsheet,
    making changes, then saving & closing).
  - Always use get_db() as a context manager (with statement) so sessions
    are properly closed even if an error occurs.
"""

from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from config.settings import DATABASE_URL, DEBUG
from database.models import Base
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Engine ────────────────────────────────────────────────────────────────────
# connect_args is SQLite-specific; needed for multi-threaded access
engine = create_engine(
    DATABASE_URL,
    echo=DEBUG,                          # Print SQL to console when DEBUG=true
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,  # We manually commit so we can rollback on errors
    autoflush=False,
    bind=engine,
)


def init_db() -> None:
    """
    Create all tables defined in models.py (if they don't exist yet).
    Call this once at application startup.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables initialised.")


@contextmanager
def get_db() -> Session:
    """
    Provide a transactional database session.

    Usage:
        with get_db() as db:
            db.add(some_record)
            # session auto-commits on exit, rolls back on exception

    This is called a "context manager" — the code after 'yield' always runs,
    even if an error happens, so the session is always properly closed.
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()          # Save all changes if no error
    except Exception as exc:
        session.rollback()        # Undo all changes if something went wrong
        logger.error(f"DB session error, rolling back: {exc}")
        raise
    finally:
        session.close()           # Always free the connection