"""Services for source management and daily collection."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.agents.collector import CollectionResult, CollectorAgent
from app.core.config import Settings, SourceConfig, append_source, get_settings, load_sources
from app.core.database import session_scope
from app.core.repositories import SourceRepository


def sync_sources(settings: Settings | None = None) -> int:
    """Reconcile ``sources.yaml`` into the database.

    Returns:
        The number of sources in the catalogue.
    """
    settings = settings or get_settings()
    with session_scope(settings) as session:
        return CollectorAgent(session, settings=settings).sync_catalogue()


def run_collection(
    *, only: str | None = None, trigger: str = "manual", settings: Settings | None = None
) -> CollectionResult:
    """Sync the catalogue then run a full collection pass."""
    settings = settings or get_settings()
    with session_scope(settings) as session:
        agent = CollectorAgent(session, settings=settings)
        agent.sync_catalogue()
        return agent.collect(only=only, trigger=trigger)


def list_sources(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Return every source in the database with its health status."""
    settings = settings or get_settings()
    with session_scope(settings) as session:
        return [
            {
                "slug": source.slug,
                "name": source.name,
                "group": source.group,
                "quality_weight": source.quality_weight,
                "is_active": source.is_active,
                "failures": source.consecutive_failures,
                "last_success_at": (
                    source.last_success_at.strftime("%Y-%m-%d %H:%M")
                    if source.last_success_at
                    else None
                ),
                "feed_url": source.feed_url,
            }
            for source in SourceRepository(session).list_all()
        ]


def add_source(config: SourceConfig, settings: Settings | None = None) -> SourceConfig:
    """Append a source to ``sources.yaml`` and insert it into the database.

    The YAML file stays the source of truth, so the write happens there first;
    the database row is then created from the reloaded catalogue.

    Raises:
        ValueError: If the slug already exists in the catalogue.
    """
    settings = settings or get_settings()
    append_source(config, settings=settings)

    catalogue = load_sources(settings=settings)
    stored = catalogue.by_slug(config.slug)
    if stored is None:  # pragma: no cover — defensive
        raise RuntimeError(f"Source {config.slug!r} was written but could not be reloaded")

    with session_scope(settings) as session:
        SourceRepository(session).upsert(**stored.to_orm_fields())

    logger.info("Source {} added to catalogue and database", config.slug)
    return stored
