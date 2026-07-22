"""Database bootstrap and statistics services."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.core.config import Settings, get_settings
from app.core.database import drop_db, init_db, session_scope
from app.core.repositories import (
    ArticleRepository,
    CategoryRepository,
    EmailRepository,
    JobRepository,
    ReportRepository,
    SourceRepository,
)


def bootstrap_database(
    settings: Settings | None = None, *, rebuild: bool = False
) -> dict[str, int]:
    """Ensure the schema exists and seed reference data.

    Args:
        settings: Configuration override, mainly for tests.
        rebuild: Drop every table first. Destructive.

    Returns:
        A summary of what was created.
    """
    settings = settings or get_settings()
    if rebuild:
        drop_db(settings)
    init_db(settings)

    with session_scope(settings) as session:
        created = CategoryRepository(session).seed_defaults()

    logger.info("Bootstrap complete (categories created: {})", created)
    return {"categories_created": created}


def collect_stats(settings: Settings | None = None) -> dict[str, Any]:
    """Gather database statistics for the ``stats`` CLI command."""
    settings = settings or get_settings()
    with session_scope(settings) as session:
        articles = ArticleRepository(session)
        sources = SourceRepository(session)
        reports = ReportRepository(session)
        emails = EmailRepository(session)
        jobs = JobRepository(session)

        return {
            "database": str(settings.database_path),
            "sources_total": sources.count(),
            "sources_active": len(sources.list_active()),
            "articles_total": articles.count(),
            "articles_by_status": articles.count_by_status(),
            "reports_total": reports.count(),
            "emails_total": emails.count(),
            "jobs_total": jobs.count(),
            "recent_jobs": [
                {"name": job.name, "status": str(job.status), "started_at": str(job.started_at)}
                for job in jobs.list_recent(limit=5)
            ],
        }
