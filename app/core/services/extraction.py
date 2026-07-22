"""Service for running the extraction pipeline stage."""

from __future__ import annotations

from app.agents.extractor import ExtractionResult, ExtractorAgent
from app.core.config import Settings, get_settings
from app.core.database import session_scope


def run_extraction(
    *, limit: int | None = None, trigger: str = "manual", settings: Settings | None = None
) -> ExtractionResult:
    """Extract full-text content for every article awaiting it."""
    settings = settings or get_settings()
    with session_scope(settings) as session:
        agent = ExtractorAgent(session, settings=settings)
        return agent.extract(limit=limit, trigger=trigger)
