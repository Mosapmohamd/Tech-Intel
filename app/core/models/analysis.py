"""LLM analysis outputs: Summary, Insight, and Score."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.models.article import Article


class _LLMOutputMixin:
    """Provenance columns shared by every LLM-generated record.

    Recording the model and prompt version makes results reproducible and lets
    us re-run only the records produced by an outdated prompt.
    """

    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    generation_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)


class Summary(_LLMOutputMixin, TimestampMixin, Base):
    """Arabic title, summary, and key points for one article."""

    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    title_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    summary_ar: Mapped[str] = mapped_column(Text, nullable=False)
    key_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    article: Mapped[Article] = relationship(back_populates="summary")

    def __repr__(self) -> str:
        return f"<Summary article_id={self.article_id} words={self.word_count}>"


class Insight(_LLMOutputMixin, TimestampMixin, Base):
    """The 'so what?' analysis: why this matters and what to do about it."""

    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    who_should_care: Mapped[str] = mapped_column(Text, nullable=False)
    technical_impact: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    impact_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    article: Mapped[Article] = relationship(back_populates="insight")

    def __repr__(self) -> str:
        return f"<Insight article_id={self.article_id} impact={self.impact_level}>"


class Score(TimestampMixin, Base):
    """Every component of the importance score, stored separately.

    Keeping the raw components (not just the total) means weights can be
    retuned and scores recomputed without re-running the LLM. The weights that
    produced ``final_score`` are snapshotted for auditability.
    """

    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    source_quality: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recency: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cross_source: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    technical_impact: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    weights_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    article: Mapped[Article] = relationship(back_populates="score")

    def __repr__(self) -> str:
        return f"<Score article_id={self.article_id} final={self.final_score:.1f}>"
