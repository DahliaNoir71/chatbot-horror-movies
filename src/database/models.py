"""SQLAlchemy models for HorrorBot database with pgvector support."""

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship

# Constantes pour les noms de tables et clés étrangères
CASCADE_ALL_DELETE_ORPHAN = "all, delete-orphan"

# Noms de tables
FILMS_TABLE = "films"


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# ============================================================================
# REFERENCE TABLES
# ============================================================================


class Collection(Base):
    """Movie collection/franchise (Halloween, Saw, Scream...)."""

    __tablename__ = "collections"

    id = Column(Integer, primary_key=True)
    tmdb_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    overview = Column(Text, nullable=True)
    poster_path = Column(String(255), nullable=True)
    backdrop_path = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.now)
    updated_at = Column(TIMESTAMP, default=datetime.now, onupdate=datetime.now)

    # Relationships
    films = relationship("Film", back_populates="collection")


class Genre(Base):
    """Movie genre (Horror, Thriller, Mystery...)."""

    __tablename__ = "genres"

    id = Column(Integer, primary_key=True)
    tmdb_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)

    # Relationships
    films = relationship("Film", secondary="film_genres", back_populates="genres")


class Keyword(Base):
    """Thematic keyword (slasher, zombie, supernatural...)."""

    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True)
    tmdb_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)

    # Relationships
    films = relationship("Film", secondary="film_keywords", back_populates="keywords")


class Studio(Base):
    """Production studio (Blumhouse, A24, Hammer...)."""

    __tablename__ = "studios"

    id = Column(Integer, primary_key=True)
    tmdb_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    logo_path = Column(String(255), nullable=True)
    origin_country = Column(String(10), nullable=True)

    # Relationships
    films = relationship("Film", secondary="film_studios", back_populates="studios")


class Language(Base):
    """Spoken language."""

    __tablename__ = "languages"

    id = Column(Integer, primary_key=True)
    iso_639_1 = Column(String(10), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    english_name = Column(String(100), nullable=True)


class Person(Base):
    """Person (actor, director, writer...)."""

    __tablename__ = "persons"

    id = Column(Integer, primary_key=True)
    tmdb_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    profile_path = Column(String(255), nullable=True)
    known_for_department = Column(String(100), nullable=True)
    popularity = Column(Float, default=0.0)
    created_at = Column(TIMESTAMP, default=datetime.now)

    # Relationships
    cast_credits = relationship("FilmCast", back_populates="person")
    crew_credits = relationship("FilmCrew", back_populates="person")


# ============================================================================
# MAIN TABLE: FILMS
# ============================================================================


class Film(Base):
    """Main film table with TMDB and RT data."""

    __tablename__ = "films"

    id = Column(Integer, primary_key=True)
    tmdb_id = Column(Integer, unique=True, nullable=False, index=True)
    imdb_id = Column(String(12), nullable=True, index=True)

    # Basic info
    title = Column(String(500), nullable=False)
    original_title = Column(String(500), nullable=True)
    year = Column(Integer, nullable=False, index=True)
    release_date = Column(Date, nullable=True)
    overview = Column(Text, nullable=True)
    tagline = Column(String(500), nullable=True)
    runtime = Column(Integer, nullable=True)
    status = Column(String(50), default="Released")

    # TMDB scores
    vote_average = Column(Float, nullable=True, index=True)
    vote_count = Column(Integer, default=0)
    popularity = Column(Float, default=0.0, index=True)

    # Financial data
    budget = Column(BigInteger, default=0)
    revenue = Column(BigInteger, default=0)

    # Media and links
    original_language = Column(String(10), nullable=True)
    poster_path = Column(String(255), nullable=True)
    backdrop_path = Column(String(255), nullable=True)
    homepage = Column(Text, nullable=True)

    # Rotten Tomatoes scores (current snapshot)
    tomatometer_score = Column(Integer, nullable=True, index=True)
    audience_score = Column(Integer, nullable=True)
    critics_consensus = Column(Text, nullable=True)
    certified_fresh = Column(Boolean, default=False)
    critics_count = Column(Integer, default=0)
    audience_count = Column(Integer, default=0)
    rotten_tomatoes_url = Column(Text, nullable=True)

    # Data source tracking
    source = Column(String(50), default="tmdb")

    # FK Collection
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True)

    # Audit
    created_at = Column(TIMESTAMP, default=datetime.now)
    updated_at = Column(TIMESTAMP, default=datetime.now, onupdate=datetime.now)

    # Constraints
    __table_args__ = (
        CheckConstraint("year >= 1888 AND year <= 2030", name="check_year_range"),
        CheckConstraint(
            "vote_average IS NULL OR (vote_average >= 0 AND vote_average <= 10)",
            name="check_vote_average",
        ),
        CheckConstraint(
            "tomatometer_score IS NULL OR (tomatometer_score >= 0 AND tomatometer_score <= 100)",
            name="check_tomatometer",
        ),
        CheckConstraint(
            "audience_score IS NULL OR (audience_score >= 0 AND audience_score <= 100)",
            name="check_audience",
        ),
    )

    # Relationships
    collection = relationship("Collection", back_populates="films")
    genres = relationship("Genre", secondary="film_genres", back_populates="films")
    keywords = relationship("Keyword", secondary="film_keywords", back_populates="films")
    studios = relationship("Studio", secondary="film_studios", back_populates="films")
    cast = relationship("FilmCast", back_populates="film", cascade=CASCADE_ALL_DELETE_ORPHAN)
    crew = relationship("FilmCrew", back_populates="film", cascade=CASCADE_ALL_DELETE_ORPHAN)
    embeddings = relationship(
        "FilmEmbedding", back_populates="film", cascade=CASCADE_ALL_DELETE_ORPHAN
    )
    rt_history = relationship(
        "RTScoreHistory", back_populates="film", cascade=CASCADE_ALL_DELETE_ORPHAN
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "tmdb_id": self.tmdb_id,
            "imdb_id": self.imdb_id,
            "title": self.title,
            "year": self.year,
            "overview": self.overview,
            "tomatometer_score": self.tomatometer_score,
            "vote_average": self.vote_average,
            "genres": [g.name for g in self.genres],
            "directors": [c.person.name for c in self.crew if c.job == "Director"],
        }

    def to_rag_context(self) -> str:
        """Generate RAG context string for embedding."""
        parts = [f"{self.title} ({self.year})"]

        if self.critics_consensus:
            parts.append(self.critics_consensus)
        elif self.overview:
            parts.append(self.overview)

        directors = [c.person.name for c in self.crew if c.job == "Director"]
        if directors:
            parts.append(f"Directed by {', '.join(directors)}")

        top_cast = sorted(self.cast, key=lambda x: x.cast_order or 999)[:3]
        if top_cast:
            cast_names = [c.person.name for c in top_cast]
            parts.append(f"Starring {', '.join(cast_names)}")

        if self.genres:
            parts.append(f"Genres: {', '.join(g.name for g in self.genres)}")

        if self.keywords:
            kw_names = [k.name for k in self.keywords[:10]]
            parts.append(f"Keywords: {', '.join(kw_names)}")

        return " | ".join(parts)


# ============================================================================
# ASSOCIATION TABLES
# ============================================================================


class FilmGenre(Base):
    """Association table: Film <-> Genre."""

    __tablename__ = "film_genres"

    film_id = Column(Integer, ForeignKey(f"{FILMS_TABLE}.id", ondelete="CASCADE"), primary_key=True)
    genre_id = Column(Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True)


class FilmKeyword(Base):
    """Association table: Film <-> Keyword."""

    __tablename__ = "film_keywords"

    film_id = Column(Integer, ForeignKey(f"{FILMS_TABLE}.id", ondelete="CASCADE"), primary_key=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id", ondelete="CASCADE"), primary_key=True)


class FilmStudio(Base):
    """Association table: Film <-> Studio."""

    __tablename__ = "film_studios"

    film_id = Column(Integer, ForeignKey(f"{FILMS_TABLE}.id", ondelete="CASCADE"), primary_key=True)
    studio_id = Column(Integer, ForeignKey("studios.id", ondelete="CASCADE"), primary_key=True)


class FilmLanguage(Base):
    """Association table: Film <-> Language."""

    __tablename__ = "film_languages"

    film_id = Column(Integer, ForeignKey(f"{FILMS_TABLE}.id", ondelete="CASCADE"), primary_key=True)
    language_id = Column(Integer, ForeignKey("languages.id", ondelete="CASCADE"), primary_key=True)
    language_type = Column(String(20), nullable=False, default="spoken", primary_key=True)


class FilmCast(Base):
    """Film cast member with role."""

    __tablename__ = "film_cast"

    id = Column(Integer, primary_key=True)
    film_id = Column(
        Integer, ForeignKey(f"{FILMS_TABLE}.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id = Column(
        Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character = Column(String(500), nullable=True)
    cast_order = Column(Integer, default=999)
    credit_id = Column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint("film_id", "person_id", "character", name="uq_film_cast"),
        Index("idx_film_cast_order", "film_id", "cast_order"),
    )

    # Relationships
    film = relationship("Film", back_populates="cast")
    person = relationship("Person", back_populates="cast_credits")


class FilmCrew(Base):
    """Film crew member with job."""

    __tablename__ = "film_crew"

    id = Column(Integer, primary_key=True)
    film_id = Column(
        Integer, ForeignKey(f"{FILMS_TABLE}.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id = Column(
        Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job = Column(String(255), nullable=False, index=True)
    department = Column(String(100), nullable=False)
    credit_id = Column(String(50), nullable=True)

    __table_args__ = (UniqueConstraint("film_id", "person_id", "job", name="uq_film_crew"),)

    # Relationships
    film = relationship("Film", back_populates="crew")
    person = relationship("Person", back_populates="crew_credits")


# ============================================================================
# HISTORY & EMBEDDINGS
# ============================================================================


class RTScoreHistory(Base):
    """Historical RT scores for tracking changes."""

    __tablename__ = "rt_score_history"

    id = Column(Integer, primary_key=True)
    film_id = Column(
        Integer, ForeignKey(f"{FILMS_TABLE}.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_date = Column(Date, nullable=False, default=date.today, index=True)
    tomatometer_score = Column(Integer, nullable=True)
    audience_score = Column(Integer, nullable=True)
    critics_count = Column(Integer, default=0)
    audience_count = Column(Integer, default=0)
    critics_consensus = Column(Text, nullable=True)
    certified_fresh = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("film_id", "snapshot_date", name="uq_rt_history"),
        CheckConstraint(
            "tomatometer_score IS NULL OR (tomatometer_score >= 0 AND tomatometer_score <= 100)",
            name="check_history_tomatometer",
        ),
    )

    # Relationships
    film = relationship("Film", back_populates="rt_history")


class FilmEmbedding(Base):
    """Vector embeddings for semantic search."""

    __tablename__ = "film_embeddings"

    id = Column(Integer, primary_key=True)
    film_id = Column(
        Integer, ForeignKey(f"{FILMS_TABLE}.id", ondelete="CASCADE"), nullable=False, index=True
    )
    embedding_type = Column(String(50), nullable=False, index=True)
    model_name = Column(String(100), nullable=False, default="all-MiniLM-L6-v2")
    embedding = Column(Vector(384), nullable=False)
    text_hash = Column(String(64), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("film_id", "embedding_type", "model_name", name="uq_embedding"),
        Index("idx_embeddings_type_model", "embedding_type", "model_name"),
    )

    # Relationships
    film = relationship("Film", back_populates="embeddings")
