"""SQLAlchemy declarative base and common mixins.

Provides the foundation for all ORM models with common
columns and behaviors.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    All models should inherit from this class to be part
    of the same metadata and support table creation.
    """

    pass


class TimestampMixin:
    """Mixin providing created_at and updated_at timestamps.

    Automatically sets created_at on insert and updates
    updated_at on every update.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ExtractedAtMixin:
    """Mixin for ETL extraction timestamp."""

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
