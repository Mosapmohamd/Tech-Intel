"""Repositories for sources and the category taxonomy."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from app.core.database.base import utcnow
from app.core.models.article import Category
from app.core.models.enums import CATEGORY_LABELS, CategorySlug
from app.core.models.source import Source
from app.core.repositories.base import BaseRepository


class SourceRepository(BaseRepository[Source]):
    """Data access for RSS sources."""

    model = Source

    def get_by_slug(self, slug: str) -> Source | None:
        """Fetch a source by its stable slug."""
        return self.find_one_by(slug=slug)

    def list_active(self) -> Sequence[Source]:
        """Return every enabled source, ordered by group then name."""
        stmt = select(Source).where(Source.is_active.is_(True)).order_by(Source.group, Source.name)
        return self.session.scalars(stmt).all()

    def upsert(self, **fields: object) -> Source:
        """Create a source or update the existing one with the same slug.

        Lets ``sources.yaml`` act as the declarative source of truth without
        creating duplicates on every startup.
        """
        slug = str(fields["slug"])
        source = self.get_by_slug(slug)
        if source is None:
            source = Source(**fields)
            return self.add(source)
        for key, value in fields.items():
            setattr(source, key, value)
        self.session.flush()
        return source

    def mark_success(self, source: Source, *, when: datetime | None = None) -> None:
        """Record a successful fetch and clear the failure counter."""
        moment = when or utcnow()
        source.last_fetched_at = moment
        source.last_success_at = moment
        source.consecutive_failures = 0
        source.last_error = None
        self.session.flush()

    def mark_failure(self, source: Source, error: str, *, when: datetime | None = None) -> None:
        """Record a failed fetch attempt."""
        source.last_fetched_at = when or utcnow()
        source.consecutive_failures += 1
        source.last_error = error[:2000]
        self.session.flush()


class CategoryRepository(BaseRepository[Category]):
    """Data access for the fixed category taxonomy."""

    model = Category

    def get_by_slug(self, slug: str) -> Category | None:
        """Fetch a category by slug."""
        return self.find_one_by(slug=slug)

    def seed_defaults(self) -> int:
        """Insert any of the 15 standard categories that are missing.

        Returns:
            The number of categories created.
        """
        created = 0
        for slug, (name_en, name_ar) in CATEGORY_LABELS.items():
            if self.get_by_slug(slug) is None:
                self.add(Category(slug=slug.value, name_en=name_en, name_ar=name_ar))
                created += 1
        return created

    def get_or_create(self, slug: str) -> Category:
        """Return the category for ``slug``, falling back to ``other``."""
        category = self.get_by_slug(slug)
        if category is not None:
            return category
        fallback = self.get_by_slug(CategorySlug.OTHER.value)
        if fallback is not None:
            return fallback
        name_en, name_ar = CATEGORY_LABELS[CategorySlug.OTHER]
        return self.add(Category(slug=CategorySlug.OTHER.value, name_en=name_en, name_ar=name_ar))
