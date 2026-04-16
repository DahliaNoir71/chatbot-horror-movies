"""Film model - main entity for horror movie data.

Primary table containing film metadata from TMDB API.
"""

from datetime import date
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, ExtractedAtMixin, TimestampMixin


class Film(Base, TimestampMixin, ExtractedAtMixin):
    """Main film entity storing horror movie data.

    Attributes:
        id: Internal primary key.
        tmdb_id: TMDB identifier (main join key).
        imdb_id: IMDb identifier (format: tt1234567).
        title: Film title (original / EN).
        overview: Plot synopsis EN (used for RAG).
        title_fr: French title from TMDB translations.
        overview_fr: French plot synopsis from TMDB translations.
        alternative_titles: Alternative titles from francophone regions (FR/BE/CA/CH/LU).
        director: Denormalized director name (from credits, role_type='director').
        cast_names: Denormalized top-N cast names (from credits, role_type='actor').
        keyword_names: Denormalized keyword labels (from film_keywords ↔ keywords).
        search_vector_fr: Weighted FR tsvector, maintained by PostgreSQL trigger.
        search_vector_en: Weighted EN tsvector, maintained by PostgreSQL trigger.
    """

    __tablename__ = "films"

    # Primary keys and identifiers
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
        index=True,
    )
    imdb_id: Mapped[str | None] = mapped_column(String(20), index=True)

    # Basic information
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(500))
    release_date: Mapped[date | None] = mapped_column(Date)
    tagline: Mapped[str | None] = mapped_column(String(500))

    # Text content for RAG
    overview: Mapped[str | None] = mapped_column(Text)

    # TMDB metrics
    popularity: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    vote_average: Mapped[float] = mapped_column(Numeric(3, 1), default=0)
    vote_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    runtime: Mapped[int | None] = mapped_column(Integer)
    original_language: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(50), default="Released")
    adult: Mapped[bool] = mapped_column(Boolean, default=False)

    # Media URLs
    poster_path: Mapped[str | None] = mapped_column(String(255))
    backdrop_path: Mapped[str | None] = mapped_column(String(255))
    homepage: Mapped[str | None] = mapped_column(Text)

    # Financial data
    budget: Mapped[int] = mapped_column(BigInteger, default=0)
    revenue: Mapped[int] = mapped_column(BigInteger, default=0)

    # ETL metadata
    source: Mapped[str] = mapped_column(String(50), default="tmdb")

    # Multilingual fields (TMDB translations + alternative_titles)
    title_fr: Mapped[str | None] = mapped_column(Text)
    overview_fr: Mapped[str | None] = mapped_column(Text)
    alternative_titles: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        server_default="{}",
        default=list,
    )

    # Denormalized fields (populated by ETL loader from credits/film_keywords)
    director: Mapped[str | None] = mapped_column(Text)
    cast_names: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        server_default="{}",
        default=list,
    )
    keyword_names: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        server_default="{}",
        default=list,
    )

    # Search vectors (read-only, maintained by PostgreSQL trigger)
    # Any justifié ici : TSVECTOR n'a pas de type SQLAlchemy natif standardisé,
    # et ces colonnes ne sont jamais lues/écrites depuis l'ORM (BM25 via SQL brut).
    search_vector_fr: Mapped[Any | None] = mapped_column(
        TSVECTOR,
        info={"read_only": True},
    )
    search_vector_en: Mapped[Any | None] = mapped_column(
        TSVECTOR,
        info={"read_only": True},
    )

    __table_args__ = (
        CheckConstraint(
            "vote_average >= 0 AND vote_average <= 10",
            name="chk_vote_average",
        ),
        CheckConstraint(
            "runtime IS NULL OR (runtime > 0 AND runtime < 1000)",
            name="chk_runtime",
        ),
    )

    @property
    def year(self) -> int | None:
        """Extract year from release date."""
        return self.release_date.year if self.release_date else None

    @property
    def roi(self) -> float | None:
        """Calculate return on investment."""
        if self.budget and self.budget > 0:
            return round(self.revenue / self.budget, 2)
        return None

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Film(id={self.id}, tmdb_id={self.tmdb_id}, title='{self.title}')>"
