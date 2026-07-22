"""Repository for articles — the busiest entity in the pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from app.core.models.analysis import Score
from app.core.models.article import Article
from app.core.models.enums import ArticleStatus
from app.core.repositories.base import BaseRepository


class ArticleRepository(BaseRepository[Article]):
    """Data access for articles, including deduplication lookups."""

    model = Article

    def get_by_url_hash(self, url_hash: str) -> Article | None:
        """Exact-URL duplicate check."""
        return self.find_one_by(url_hash=url_hash)

    def find_by_content_hash(self, content_hash: str) -> Sequence[Article]:
        """Syndicated-copy duplicate check across sources."""
        return self.find_by(content_hash=content_hash)

    def exists_url_hash(self, url_hash: str) -> bool:
        """Cheap existence check used by the Collector Agent."""
        return self.exists(url_hash=url_hash)

    def list_by_status(
        self, status: ArticleStatus, *, limit: int | None = None
    ) -> Sequence[Article]:
        """Return the work queue for a given pipeline stage, oldest first."""
        stmt = (
            select(Article)
            .where(Article.status == status, Article.is_duplicate.is_(False))
            .order_by(Article.collected_at.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return self.session.scalars(stmt).all()

    def list_for_period(
        self,
        start: datetime,
        end: datetime,
        *,
        only_unreported: bool = True,
        min_status: ArticleStatus = ArticleStatus.ANALYZED,
    ) -> Sequence[Article]:
        """Return candidate articles for a weekly report window."""
        stmt = (
            select(Article)
            .where(
                Article.published_at >= start,
                Article.published_at <= end,
                Article.is_duplicate.is_(False),
                Article.status == min_status,
            )
            .order_by(Article.published_at.desc())
        )
        if only_unreported:
            stmt = stmt.where(Article.included_in_report.is_(False))
        return self.session.scalars(stmt).all()

    def list_top_scored(
        self, start: datetime, end: datetime, *, limit: int = 10, only_unreported: bool = True
    ) -> Sequence[Article]:
        """Return the highest-scoring articles in a window, ranked descending."""
        stmt = (
            select(Article)
            .join(Score, Score.article_id == Article.id)
            .where(
                Article.published_at >= start,
                Article.published_at <= end,
                Article.is_duplicate.is_(False),
            )
            .order_by(Score.final_score.desc())
            .limit(limit)
        )
        if only_unreported:
            stmt = stmt.where(Article.included_in_report.is_(False))
        return self.session.scalars(stmt).all()

    def mark_duplicate(self, article: Article, original: Article) -> None:
        """Link a duplicate to its original and bump the original's mention count."""
        article.is_duplicate = True
        article.duplicate_of_id = original.id
        article.status = ArticleStatus.DUPLICATE
        original.mention_count += 1
        self.session.flush()

    def mark_reported(self, articles: Sequence[Article]) -> None:
        """Flag articles as already delivered so they aren't repeated next week."""
        for article in articles:
            article.included_in_report = True
        self.session.flush()

    def count_by_status(self) -> dict[str, int]:
        """Return a ``{status: count}`` breakdown for the ``stats`` command."""
        rows = self.session.execute(
            select(Article.status, func.count(Article.id)).group_by(Article.status)
        ).all()
        return {str(status): count for status, count in rows}

    def count_by_source(self) -> dict[int, int]:
        """Return a ``{source_id: count}`` breakdown."""
        rows = self.session.execute(
            select(Article.source_id, func.count(Article.id)).group_by(Article.source_id)
        ).all()
        return {int(source_id): count for source_id, count in rows}
