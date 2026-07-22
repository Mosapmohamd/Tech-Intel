"""Database engine, session factory, and schema lifecycle helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from loguru import logger
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config.settings import Settings, get_settings
from app.core.database.base import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _configure_sqlite(dbapi_connection: Any, _record: Any) -> None:
    """Enable foreign keys and WAL mode on every new SQLite connection.

    SQLite disables foreign-key enforcement by default, which would silently
    allow orphaned rows. WAL mode lets the scheduler read while a pipeline writes.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_engine(settings: Settings | None = None) -> Engine:
    """Return the process-wide SQLAlchemy engine, creating it on first use."""
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        settings.ensure_directories()
        _engine = create_engine(
            settings.database_url,
            echo=settings.database_echo,
            future=True,
            connect_args={"check_same_thread": False},
        )
        event.listen(_engine, "connect", _configure_sqlite)
        logger.debug("Database engine created at {}", settings.database_path)
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Return the process-wide session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(settings), expire_on_commit=False, autoflush=False
        )
    return _session_factory


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    Commits on success, rolls back on any exception, and always closes.
    """
    session = get_session_factory(settings)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Transaction rolled back")
        raise
    finally:
        session.close()


def init_db(settings: Settings | None = None) -> None:
    """Create any missing tables. Safe to call repeatedly."""
    import app.core.models  # noqa: F401  (registers all mappers)

    Base.metadata.create_all(bind=get_engine(settings))
    logger.info("Database schema ensured ({} tables)", len(Base.metadata.tables))


def drop_db(settings: Settings | None = None) -> None:
    """Drop every table. Destructive — used by the ``rebuild-db`` command."""
    import app.core.models  # noqa: F401

    Base.metadata.drop_all(bind=get_engine(settings))
    logger.warning("All database tables dropped")


def reset_state() -> None:
    """Discard cached engine/session factory. Used by tests."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
