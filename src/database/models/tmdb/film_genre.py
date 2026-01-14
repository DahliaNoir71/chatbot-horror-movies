"""FilmGenre association table.

Many-to-many relationship between Film and Genre.
"""

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class FilmGenre(Base):
    """Association table for Film-Genre relationship.

    Attributes:
        film_id: Foreign key to films.
        genre_id: Foreign key to genres.
    """

    __tablename__ = "film_genres"

    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("films.id", ondelete="CASCADE"),
        primary_key=True,
    )
    genre_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True,
    )
