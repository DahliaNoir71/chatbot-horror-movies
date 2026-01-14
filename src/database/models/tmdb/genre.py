"""Genre model for TMDB film classification.

Stores genre definitions from TMDB API (e.g., Horror=27).
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class Genre(Base):
    """Film genre reference table.

    Attributes:
        id: Primary key.
        tmdb_genre_id: TMDB genre identifier (e.g., 27 for Horror).
        name: Genre display name.
        created_at: Creation timestamp.
    """

    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_genre_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Genre(id={self.id}, name='{self.name}')>"
