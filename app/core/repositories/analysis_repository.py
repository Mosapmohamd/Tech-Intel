"""Repositories for analysis outputs, reports, email history, and jobs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.database.base import utcnow
from app.core.models.analysis import Insight, Score, Summary
from app.core.models.enums import DeliveryStatus, JobStatus, ReportStatus
from app.core.models.report import EmailHistory, JobRun, ReportArticle, WeeklyReport
from app.core.repositories.base import BaseRepository


class SummaryRepository(BaseRepository[Summary]):
    """Data access for Arabic summaries."""

    model = Summary

    def get_for_article(self, article_id: int) -> Summary | None:
        """Return the summary attached to an article, if any."""
        return self.find_one_by(article_id=article_id)


class InsightRepository(BaseRepository[Insight]):
    """Data access for article insights."""

    model = Insight

    def get_for_article(self, article_id: int) -> Insight | None:
        """Return the insight attached to an article, if any."""
        return self.find_one_by(article_id=article_id)


class ScoreRepository(BaseRepository[Score]):
    """Data access for article scores."""

    model = Score

    def get_for_article(self, article_id: int) -> Score | None:
        """Return the score attached to an article, if any."""
        return self.find_one_by(article_id=article_id)

    def upsert(self, article_id: int, **components: Any) -> Score:
        """Create or replace the score for an article."""
        score = self.get_for_article(article_id)
        if score is None:
            return self.add(Score(article_id=article_id, **components))
        for key, value in components.items():
            setattr(score, key, value)
        self.session.flush()
        return score


class ReportRepository(BaseRepository[WeeklyReport]):
    """Data access for weekly reports and their article placements."""

    model = WeeklyReport

    def get_for_period(self, start: datetime, end: datetime) -> WeeklyReport | None:
        """Return the report covering an exact period, if it exists."""
        return self.find_one_by(period_start=start, period_end=end)

    def latest(self) -> WeeklyReport | None:
        """Return the most recently generated report."""
        stmt = select(WeeklyReport).order_by(WeeklyReport.period_end.desc()).limit(1)
        return self.session.scalars(stmt).first()

    def latest_by_status(self, status: ReportStatus) -> WeeklyReport | None:
        """Return the most recent report in a given state."""
        stmt = (
            select(WeeklyReport)
            .where(WeeklyReport.status == status)
            .order_by(WeeklyReport.period_end.desc())
            .limit(1)
        )
        return self.session.scalars(stmt).first()

    def attach_article(
        self, report: WeeklyReport, article_id: int, *, section: str, rank: int, score: float
    ) -> ReportArticle:
        """Place an article into a report section at a given rank."""
        link = ReportArticle(
            report_id=report.id,
            article_id=article_id,
            section=section,
            rank=rank,
            score_at_selection=score,
        )
        self.session.add(link)
        self.session.flush()
        return link


class EmailRepository(BaseRepository[EmailHistory]):
    """Data access for email delivery history."""

    model = EmailHistory

    def list_recent(self, limit: int = 20) -> Sequence[EmailHistory]:
        """Return the most recent delivery attempts."""
        stmt = select(EmailHistory).order_by(EmailHistory.created_at.desc()).limit(limit)
        return self.session.scalars(stmt).all()

    def record_success(self, entry: EmailHistory) -> None:
        """Mark a delivery attempt as sent."""
        entry.status = DeliveryStatus.SENT
        entry.sent_at = utcnow()
        entry.attempts += 1
        self.session.flush()

    def record_failure(self, entry: EmailHistory, error: str) -> None:
        """Mark a delivery attempt as failed."""
        entry.status = DeliveryStatus.FAILED
        entry.attempts += 1
        entry.error_message = error[:2000]
        self.session.flush()


class JobRepository(BaseRepository[JobRun]):
    """Data access for pipeline job audit records."""

    model = JobRun

    def start(self, name: str, *, trigger: str = "manual") -> JobRun:
        """Open a new job record in the RUNNING state."""
        return self.add(JobRun(name=name, trigger=trigger, started_at=utcnow()))

    def finish(
        self,
        job: JobRun,
        *,
        status: JobStatus,
        processed: int = 0,
        failed: int = 0,
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Close a job record with its outcome and duration."""
        job.finished_at = utcnow()
        job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
        job.status = status
        job.items_processed = processed
        job.items_failed = failed
        job.details = details or {}
        job.error_message = error[:2000] if error else None
        self.session.flush()

    def list_recent(self, limit: int = 10) -> Sequence[JobRun]:
        """Return the most recent job runs."""
        stmt = select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
        return self.session.scalars(stmt).all()
