"""Data access layer (repository pattern)."""

from app.core.repositories.analysis_repository import (
    EmailRepository,
    InsightRepository,
    JobRepository,
    ReportRepository,
    ScoreRepository,
    SummaryRepository,
)
from app.core.repositories.article_repository import ArticleRepository
from app.core.repositories.base import BaseRepository
from app.core.repositories.source_repository import CategoryRepository, SourceRepository

__all__ = [
    "ArticleRepository",
    "BaseRepository",
    "CategoryRepository",
    "EmailRepository",
    "InsightRepository",
    "JobRepository",
    "ReportRepository",
    "ScoreRepository",
    "SourceRepository",
    "SummaryRepository",
]
