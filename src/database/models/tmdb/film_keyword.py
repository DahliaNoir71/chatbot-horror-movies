"""FilmKeyword association table.

Many-to-many relationship between Film and Keyword
with source tracking.
"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class FilmKeyword(Base):
    """Association table for Film-Keyword relationship.

    Attributes:
        film_id: Foreign key to films.
        keyword_id: Foreign key to keywords.
        source: Origin of the keyword (tmdb or kaggle).
    """

    __tablename__ = "film_keywords"

    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("films.id", ondelete="CASCADE"),
        primary_key=True,
    )
    keyword_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source: Mapped[str] = mapped_column(
        String(50),
        default="tmdb",
    )
