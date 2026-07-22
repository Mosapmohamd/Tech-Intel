"""SQLAlchemy ORM models.

Importing this package registers every mapper with the declarative ``Base``,
which is why :func:`app.core.database.init_db` imports it before ``create_all``.
"""

from app.core.models.analysis import Insight, Score, Summary
from app.core.models.article import Article, ArticleCategory, Category
from app.core.models.enums import (
    CATEGORY_LABELS,
    ArticleStatus,
    CategorySlug,
    DeliveryStatus,
    JobStatus,
    ReportSection,
    ReportStatus,
)
from app.core.models.report import EmailHistory, JobRun, ReportArticle, WeeklyReport
from app.core.models.source import Source

__all__ = [
    "Article",
    "ArticleCategory",
    "ArticleStatus",
    "CATEGORY_LABELS",
    "Category",
    "CategorySlug",
    "DeliveryStatus",
    "EmailHistory",
    "Insight",
    "JobRun",
    "JobStatus",
    "ReportArticle",
    "ReportSection",
    "ReportStatus",
    "Score",
    "Source",
    "Summary",
    "WeeklyReport",
]
