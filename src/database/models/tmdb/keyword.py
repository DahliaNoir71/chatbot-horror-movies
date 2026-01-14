"""Keyword model for TMDB semantic tags.

Stores keywords like 'slasher', 'found-footage', 'zombie'
valuable for RAG semantic search.
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class Keyword(Base):
    """Semantic keyword for films.

    Attributes:
        id: Primary key.
        tmdb_keyword_id: TMDB keyword identifier.
        name: Keyword text.
    """

    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_keyword_id: Mapped[int | None] = mapped_column(
        Integer,
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Keyword(id={self.id}, name='{self.name}')>"
