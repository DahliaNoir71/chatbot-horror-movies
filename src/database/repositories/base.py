"""
Base repository with generic CRUD operations.

Provides a reusable base class for all repositories with
common database operations.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.models.base import Base

# Type alias for valid database field values
FieldValue = str | int | float | bool | date | datetime | Decimal | UUID | None

# Generic type variable bound to Base model
ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic repository providing common CRUD operations.

    Attributes:
        model: SQLAlchemy model class.
        session: Database session.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session

    @property
    def session(self) -> Session:
        """Get the database session."""
        return self._session

    def get_by_id(self, entity_id: int) -> ModelT | None:
        """Retrieve entity by primary key.

        Args:
            entity_id: Primary key value.

        Returns:
            Entity instance or None if not found.
        """
        return self._session.get(self.model, entity_id)

    def get_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        """Retrieve all entities with pagination.

        Args:
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of entity instances.
        """
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self._session.scalars(stmt).all())

    def get_by_field(self, field_name: str, value: FieldValue) -> ModelT | None:
        """Retrieve entity by a specific field value.

        Args:
            field_name: Name of the field to filter on.
            value: Value to match.

        Returns:
            Entity instance or None if not found.
        """
        field = getattr(self.model, field_name)
        stmt = select(self.model).where(field == value)
        return self._session.scalars(stmt).first()

    def get_many_by_field(
        self,
        field_name: str,
        value: FieldValue,
        limit: int = 100,
    ) -> list[ModelT]:
        """Retrieve multiple entities by a specific field value.

        Args:
            field_name: Name of the field to filter on.
            value: Value to match.
            limit: Maximum number of results.

        Returns:
            List of entity instances.
        """
        field = getattr(self.model, field_name)
        stmt = select(self.model).where(field == value).limit(limit)
        return list(self._session.scalars(stmt).all())

    def exists(self, entity_id: int) -> bool:
        """Check if entity exists by primary key.

        Args:
            entity_id: Primary key value.

        Returns:
            True if entity exists.
        """
        return self.get_by_id(entity_id) is not None

    def count(self) -> int:
        """Count total number of entities.

        Returns:
            Total count.
        """
        stmt = select(func.count()).select_from(self.model)
        result = self._session.execute(stmt).scalar()
        return result or 0

    def create(self, entity: ModelT) -> ModelT:
        """Create a new entity.

        Args:
            entity: Entity instance to persist.

        Returns:
            Persisted entity with generated ID.
        """
        self._session.add(entity)
        self._session.flush()
        return entity

    def create_many(self, entities: list[ModelT]) -> list[ModelT]:
        """Create multiple entities in batch.

        Args:
            entities: List of entity instances.

        Returns:
            List of persisted entities.
        """
        self._session.add_all(entities)
        self._session.flush()
        return entities

    def update(self, entity: ModelT) -> ModelT:
        """Update an existing entity.

        Args:
            entity: Entity instance with updated values.

        Returns:
            Updated entity.
        """
        self._session.merge(entity)
        self._session.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        """Delete an entity.

        Args:
            entity: Entity instance to delete.
        """
        self._session.delete(entity)
        self._session.flush()

    def delete_by_id(self, entity_id: int) -> bool:
        """Delete entity by primary key.

        Args:
            entity_id: Primary key value.

        Returns:
            True if entity was deleted, False if not found.
        """
        entity = self.get_by_id(entity_id)
        if entity:
            self.delete(entity)
            return True
        return False

    def commit(self) -> None:
        """Commit current transaction."""
        self._session.commit()

    def rollback(self) -> None:
        """Rollback current transaction."""
        self._session.rollback()
