"""Shared pytest fixtures.

Every test gets a throwaway SQLite file and a fresh engine, so tests never
touch the developer's real database and can run in any order.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_session_factory, init_db, reset_state, session_scope
from app.core.repositories import CategoryRepository


@pytest.fixture
def settings(tmp_path: Path) -> Iterator[Settings]:
    """Settings pointed at a temporary database and log directory."""
    reset_state()
    cfg = Settings(
        database_path=tmp_path / "test.db",
        log_dir=tmp_path / "logs",
        _env_file=None,  # type: ignore[call-arg]
    )
    yield cfg
    reset_state()


@pytest.fixture
def db(settings: Settings) -> Iterator[Session]:
    """An initialized database session with the category taxonomy seeded.

    The test session is rolled back rather than committed on teardown, so
    tests that deliberately trigger an ``IntegrityError`` still tear down
    cleanly and no state leaks between tests.
    """
    init_db(settings)
    with session_scope(settings) as session:
        CategoryRepository(session).seed_defaults()

    session = get_session_factory(settings)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
