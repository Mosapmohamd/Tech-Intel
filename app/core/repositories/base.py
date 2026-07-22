"""Generic repository base class.

The repository pattern keeps SQLAlchemy queries out of the agents. Agents
depend on a repository interface, which makes them unit-testable against an
in-memory database and swappable if the storage backend ever changes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database.base import Base


class BaseRepository[ModelT: Base]:
    """CRUD operations shared by every concrete repository."""

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, entity: ModelT) -> ModelT:
        """Stage a new entity for insertion and flush to obtain its primary key."""
        self.session.add(entity)
        self.session.flush()
        return entity

    def add_all(self, entities: Sequence[ModelT]) -> Sequence[ModelT]:
        """Stage several entities in one flush."""
        self.session.add_all(entities)
        self.session.flush()
        return entities

    def get(self, entity_id: int) -> ModelT | None:
        """Fetch one entity by primary key, or ``None``."""
        return self.session.get(self.model, entity_id)

    def list_all(self, *, limit: int | None = None, offset: int = 0) -> Sequence[ModelT]:
        """Return all entities, optionally paginated."""
        stmt = select(self.model).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return self.session.scalars(stmt).all()

    def find_by(self, **filters: Any) -> Sequence[ModelT]:
        """Return entities matching simple equality filters."""
        stmt = select(self.model).filter_by(**filters)
        return self.session.scalars(stmt).all()

    def find_one_by(self, **filters: Any) -> ModelT | None:
        """Return the first entity matching simple equality filters."""
        stmt = select(self.model).filter_by(**filters).limit(1)
        return self.session.scalars(stmt).first()

    def count(self, **filters: Any) -> int:
        """Count entities, optionally filtered."""
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        return self.session.scalar(stmt) or 0

    def delete(self, entity: ModelT) -> None:
        """Mark an entity for deletion."""
        self.session.delete(entity)

    def exists(self, **filters: Any) -> bool:
        """Return whether at least one matching entity exists."""
        return self.count(**filters) > 0
