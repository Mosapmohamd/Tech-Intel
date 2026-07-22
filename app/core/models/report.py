"""Weekly report, email delivery history, and job run ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, TimestampMixin
from app.core.models.enums import DeliveryStatus, JobStatus, ReportSection, ReportStatus

if TYPE_CHECKING:
    from app.core.models.article import Article


class WeeklyReport(TimestampMixin, Base):
    """One generated weekly digest covering a date range."""

    __tablename__ = "weekly_reports"
    __table_args__ = (UniqueConstraint("period_start", "period_end"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    trends: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    recommendations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[ReportStatus] = mapped_column(
        String(20), nullable=False, default=ReportStatus.DRAFT, index=True
    )

    article_links: Mapped[list[ReportArticle]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    emails: Mapped[list[EmailHistory]] = relationship(back_populates="report")

    def __repr__(self) -> str:
        return (
            f"<WeeklyReport id={self.id} {self.period_start:%Y-%m-%d}→{self.period_end:%Y-%m-%d}>"
        )


class ReportArticle(Base):
    """Placement of an article inside a report (section + rank)."""

    __tablename__ = "report_articles"
    __table_args__ = (UniqueConstraint("report_id", "article_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("weekly_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section: Mapped[ReportSection] = mapped_column(String(30), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score_at_selection: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    report: Mapped[WeeklyReport] = relationship(back_populates="article_links")
    article: Mapped[Article] = relationship()


class EmailHistory(TimestampMixin, Base):
    """One delivery attempt, successful or not."""

    __tablename__ = "email_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_reports.id", ondelete="SET NULL"), nullable=True, index=True
    )

    recipients: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[DeliveryStatus] = mapped_column(
        String(20), nullable=False, default=DeliveryStatus.PENDING, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped[WeeklyReport | None] = relationship(back_populates="emails")

    def __repr__(self) -> str:
        return f"<EmailHistory id={self.id} status={self.status}>"


class JobRun(TimestampMixin, Base):
    """Audit record for every scheduled or manual pipeline run."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[JobStatus] = mapped_column(
        String(20), nullable=False, default=JobStatus.RUNNING, index=True
    )
    items_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<JobRun id={self.id} name={self.name!r} status={self.status}>"
