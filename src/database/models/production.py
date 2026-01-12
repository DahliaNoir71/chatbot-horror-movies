"""Production-related SQLAlchemy models.

Contains ProductionCompany, SpokenLanguage, and their
association tables. Data comes from Kaggle via Spark.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base

if TYPE_CHECKING:
    from src.database.models.film import Film


class ProductionCompany(Base):
    """Film production company/studio.

    Stores studio information like Blumhouse, A24, etc.
    Data sourced from Kaggle dataset via Spark processing.

    Attributes:
        id: Primary key.
        tmdb_company_id: TMDB company identifier.
        name: Company name.
        origin_country: ISO country code.
    """

    __tablename__ = "production_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_company_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    origin_country: Mapped[str | None] = mapped_column(String(10))

    # Relationships
    films: Mapped[list["Film"]] = relationship(
        "Film",
        secondary="film_companies",
        back_populates="production_companies",
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<ProductionCompany(id={self.id}, name='{self.name}')>"


class SpokenLanguage(Base):
    """Language spoken in films.

    Reference table for ISO 639-1 language codes.
    Data sourced from Kaggle dataset via Spark processing.

    Attributes:
        id: Primary key.
        iso_639_1: ISO language code (e.g., 'en', 'fr').
        name: Language name in English.
    """

    __tablename__ = "spoken_languages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    iso_639_1: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    films: Mapped[list["Film"]] = relationship(
        "Film",
        secondary="film_languages",
        back_populates="spoken_languages",
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<SpokenLanguage(iso='{self.iso_639_1}', name='{self.name}')>"


# =============================================================================
# ASSOCIATION TABLES
# =============================================================================


class FilmCompany(Base):
    """Association table for Film-ProductionCompany relationship."""

    __tablename__ = "film_companies"

    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("films.id", ondelete="CASCADE"),
        primary_key=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_companies.id", ondelete="CASCADE"),
        primary_key=True,
    )


class FilmLanguage(Base):
    """Association table for Film-SpokenLanguage relationship."""

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
