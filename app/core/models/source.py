"""Source ORM model — one row per configured RSS feed."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.models.article import Article


class Source(TimestampMixin, Base):
    """A news source and its feed health metadata.

    ``quality_weight`` feeds the *Source Quality* component of the scoring
    engine, and ``etag`` / ``last_modified`` enable conditional HTTP GETs so
    unchanged feeds cost nothing to poll.
    """

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    feed_url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    site_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    group: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    default_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")

    quality_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    etag: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(100), nullable=True)

    articles: Mapped[list[Article]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} slug={self.slug!r} active={self.is_active}>"
