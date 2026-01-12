"""Film-related SQLAlchemy models.

Contains the core Film model and related entities:
Genre, Credit, Keyword, and association tables.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, ExtractedAtMixin, TimestampMixin

# Foreign key references
FILM_FK = "films.id"

if TYPE_CHECKING:
    from src.database.models.production import ProductionCompany, SpokenLanguage
    from src.database.models.rotten_tomatoes import RTScore
    from src.database.models.youtube import Video


# =============================================================================
# GENRE
# =============================================================================


class Genre(Base):
    """Film genre reference table.

    Stores genre definitions from TMDB API.

    Attributes:
        id: Primary key.
        tmdb_genre_id: TMDB genre identifier (e.g., 27 for Horror).
        name: Genre display name.
    """

    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_genre_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    films: Mapped[list["Film"]] = relationship(
        "Film",
        secondary="film_genres",
        back_populates="genres",
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Genre(id={self.id}, name='{self.name}')>"


# =============================================================================
# KEYWORD
# =============================================================================


class Keyword(Base):
    """Semantic keyword for films.

    Keywords like 'slasher', 'found-footage', 'zombie' are
    valuable for RAG semantic search.

    Attributes:
        id: Primary key.
        tmdb_keyword_id: TMDB keyword identifier.
        name: Keyword text.
    """

    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_keyword_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Relationships
    films: Mapped[list["Film"]] = relationship(
        "Film",
        secondary="film_keywords",
        back_populates="keywords",
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Keyword(id={self.id}, name='{self.name}')>"


# =============================================================================
# FILM
# =============================================================================


class Film(Base, TimestampMixin, ExtractedAtMixin):
    """Main film entity storing horror movie data.

    Primary table containing film metadata from TMDB API,
    enriched with data from other sources.

    Attributes:
        id: Internal primary key.
        tmdb_id: TMDB identifier (main join key).
        imdb_id: IMDb identifier (format: tt1234567).
        title: Film title.
        overview: Plot synopsis (used for RAG).
        embedding: Vector embedding for semantic search.
    """

    __tablename__ = "films"

    # Primary keys and identifiers
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
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

    # Financial data (enriched by Spark/Kaggle)
    budget: Mapped[int] = mapped_column(BigInteger, default=0)
    revenue: Mapped[int] = mapped_column(BigInteger, default=0)

    # ETL metadata
    source: Mapped[str] = mapped_column(String(50), default="tmdb")

    # Vector embedding for RAG (1536 dimensions for OpenAI)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    # Relationships
    genres: Mapped[list["Genre"]] = relationship(
        "Genre",
        secondary="film_genres",
        back_populates="films",
    )
    keywords: Mapped[list["Keyword"]] = relationship(
        "Keyword",
        secondary="film_keywords",
        back_populates="films",
    )
    credits: Mapped[list["Credit"]] = relationship(
        "Credit",
        back_populates="film",
        cascade="all, delete-orphan",
    )
    rt_score: Mapped["RTScore | None"] = relationship(
        "RTScore",
        back_populates="film",
        uselist=False,
        cascade="all, delete-orphan",
    )
    videos: Mapped[list["Video"]] = relationship(
        "Video",
        secondary="film_videos",
        back_populates="films",
    )
    production_companies: Mapped[list["ProductionCompany"]] = relationship(
        "ProductionCompany",
        secondary="film_companies",
        back_populates="films",
    )
    spoken_languages: Mapped[list["SpokenLanguage"]] = relationship(
        "SpokenLanguage",
        secondary="film_languages",
        back_populates="films",
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint("vote_average >= 0 AND vote_average <= 10", name="chk_vote_average"),
        CheckConstraint("runtime IS NULL OR (runtime > 0 AND runtime < 1000)", name="chk_runtime"),
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


# =============================================================================
# CREDIT
# =============================================================================


class Credit(Base):
    """Film crew and cast member.

    Stores directors, actors, writers, and producers
    associated with a film.

    Attributes:
        id: Primary key.
        film_id: Foreign key to films.
        person_name: Name of the person.
        role_type: One of 'director', 'actor', 'writer', 'producer'.
        character_name: Character name (for actors).
        display_order: Order for cast listing.
    """

    __tablename__ = "credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(FILM_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tmdb_person_id: Mapped[int | None] = mapped_column(Integer)

    # Person info
    person_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Role info
    role_type: Mapped[str] = mapped_column(String(20), nullable=False)
    character_name: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(100))
    job: Mapped[str | None] = mapped_column(String(100))

    # Display order for cast
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Media
    profile_path: Mapped[str | None] = mapped_column(String(255))

    # Relationships
    film: Mapped["Film"] = relationship("Film", back_populates="credits")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "role_type IN ('director', 'actor', 'writer', 'producer')",
            name="chk_role_type",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Credit(id={self.id}, person='{self.person_name}', role='{self.role_type}')>"


# =============================================================================
# ASSOCIATION TABLES
# =============================================================================


class FilmGenre(Base):
    """Association table for Film-Genre many-to-many relationship."""

    __tablename__ = "film_genres"

    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(FILM_FK, ondelete="CASCADE"),
        primary_key=True,
    )
    genre_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True,
    )


class FilmKeyword(Base):
    """Association table for Film-Keyword many-to-many relationship.

    Includes source tracking for TMDB vs Kaggle keywords.
    """

    __tablename__ = "film_keywords"

    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(FILM_FK, ondelete="CASCADE"),
        primary_key=True,
    )
    keyword_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source: Mapped[str] = mapped_column(String(50), default="tmdb")
