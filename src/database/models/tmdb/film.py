"""Film model - main entity for horror movie data.

Primary table containing film metadata from TMDB API.
"""

from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, ExtractedAtMixin, TimestampMixin


class Film(Base, TimestampMixin, ExtractedAtMixin):
    """Main film entity storing horror movie data.

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

    # Vector embedding for RAG (1536 dimensions for OpenAI)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

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
