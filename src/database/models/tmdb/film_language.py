"""FilmLanguage association table.

Many-to-many relationship between Film and SpokenLanguage.
"""

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class FilmLanguage(Base):
    """Association table for Film-SpokenLanguage relationship.

    Attributes:
        film_id: Foreign key to films.
        language_id: Foreign key to spoken_languages.
    """

    __tablename__ = "film_languages"

    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("films.id", ondelete="CASCADE"),
        primary_key=True,
    )
    language_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("spoken_languages.id", ondelete="CASCADE"),
        primary_key=True,
    )
