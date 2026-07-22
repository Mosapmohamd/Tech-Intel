"""Article and Category ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, TimestampMixin
from app.core.models.enums import ArticleStatus

if TYPE_CHECKING:
    from app.core.models.analysis import Insight, Score, Summary
    from app.core.models.source import Source


class Category(TimestampMixin, Base):
    """A taxonomy entry from the fixed 15-category list."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    article_links: Mapped[list[ArticleCategory]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Category slug={self.slug!r}>"


class ArticleCategory(Base):
    """Association between an article and a category, with LLM confidence.

    Modeled as an explicit entity rather than a plain many-to-many table
    because the classification carries its own attributes.
    """

    __tablename__ = "article_categories"
    __table_args__ = (UniqueConstraint("article_id", "category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    article: Mapped[Article] = relationship(back_populates="category_links")
    category: Mapped[Category] = relationship(back_populates="article_links")


class Article(TimestampMixin, Base):
    """A single collected article and its extracted content.

    Deduplication uses two hashes: ``url_hash`` catches the same link arriving
    twice, while ``content_hash`` catches syndicated copies published under
    different URLs. Near-duplicates are linked via ``duplicate_of_id`` rather
    than deleted, so the Ranking Agent can count cross-source mentions.
    """

    __tablename__ = "articles"
    __table_args__ = (
        Index("ix_articles_status_published", "status", "published_at"),
        Index("ix_articles_report_flag", "included_in_report"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )

    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    feed_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[ArticleStatus] = mapped_column(
        String(20), nullable=False, default=ArticleStatus.COLLECTED, index=True
    )
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    included_in_report: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship(back_populates="articles")
    duplicate_of: Mapped[Article | None] = relationship(remote_side=[id])
    category_links: Mapped[list[ArticleCategory]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    summary: Mapped[Summary | None] = relationship(
        back_populates="article", cascade="all, delete-orphan", uselist=False
    )
    insight: Mapped[Insight | None] = relationship(
        back_populates="article", cascade="all, delete-orphan", uselist=False
    )
    score: Mapped[Score | None] = relationship(
        back_populates="article", cascade="all, delete-orphan", uselist=False
    )

    @property
    def primary_category(self) -> Category | None:
        """The highest-confidence category assigned to this article."""
        primary = [link for link in self.category_links if link.is_primary]
        chosen = primary or sorted(self.category_links, key=lambda x: x.confidence, reverse=True)
        return chosen[0].category if chosen else None

    def __repr__(self) -> str:
        return f"<Article id={self.id} status={self.status} title={self.title[:40]!r}>"
