"""Pydantic schemas for data aggregation.

Defines input schemas per source and unified output schema
for the RAG-ready aggregated film data.
"""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# =============================================================================
# CONSTANTS
# =============================================================================

IMDB_ID_PATTERN = r"^tt\d{7,8}$"
"""Regex pattern for IMDB ID validation (format: tt1234567 or tt12345678)."""


# =============================================================================
# SOURCE INPUT SCHEMAS
# =============================================================================


class TMDBFilmData(BaseModel):
    """Film data from TMDB API extraction.

    Attributes:
        tmdb_id: TMDB unique identifier (required).
        imdb_id: IMDb identifier (format: tt1234567).
        title: Film title.
        original_title: Original language title.
        release_date: Release date (YYYY-MM-DD).
        overview: Plot synopsis for RAG.
        tagline: Marketing tagline.
        popularity: TMDB popularity score.
        vote_average: Average rating (0-10).
        vote_count: Number of votes.
        runtime: Duration in minutes.
        original_language: ISO 639-1 language code.
        poster_path: TMDB poster image path.
        backdrop_path: TMDB backdrop image path.
        budget: Production budget in USD.
        revenue: Box office revenue in USD.
        genres: List of genre names.
        keywords: List of keyword tags.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    # Identifiers
    tmdb_id: int = Field(gt=0)
    imdb_id: str | None = Field(default=None, pattern=IMDB_ID_PATTERN)

    # Basic info
    title: str = Field(min_length=1, max_length=500)
    original_title: str | None = Field(default=None, max_length=500)
    release_date: date | None = None
    overview: str | None = Field(default=None, max_length=5000)
    tagline: str | None = Field(default=None, max_length=500)

    # Metrics
    popularity: float = Field(default=0.0, ge=0.0)
    vote_average: float = Field(default=0.0, ge=0.0, le=10.0)
    vote_count: int = Field(default=0, ge=0)

    # Metadata
    runtime: int | None = Field(default=None, ge=1, le=1000)
    original_language: str | None = Field(default=None, max_length=10)
    adult: bool = Field(default=False)
    status: str = Field(default="Released", max_length=50)

    # Media
    poster_path: str | None = Field(default=None, max_length=255)
    backdrop_path: str | None = Field(default=None, max_length=255)
    homepage: str | None = None

    # Financial
    budget: int = Field(default=0, ge=0)
    revenue: int = Field(default=0, ge=0)

    # Relations (denormalized for aggregation)
    genres: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    @property
    def year(self) -> int | None:
        """Extract year from release date."""
        return self.release_date.year if self.release_date else None


class RTEnrichmentData(BaseModel):
    """Rotten Tomatoes enrichment data from scraping.

    Attributes:
        tmdb_id: TMDB ID for joining.
        tomatometer_score: Critic score (0-100).
        tomatometer_state: fresh, certified_fresh, rotten.
        audience_score: Audience score (0-100).
        audience_state: Audience rating state.
        critics_consensus: Summary text (crucial for RAG).
        critics_count: Number of critic reviews.
        audience_count: Number of audience reviews.
        rt_url: Rotten Tomatoes page URL.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    # Join key
    tmdb_id: int = Field(gt=0)

    # Critic scores
    tomatometer_score: int | None = Field(default=None, ge=0, le=100)
    tomatometer_state: str | None = Field(default=None, max_length=20)
    critics_count: int = Field(default=0, ge=0)
    critics_average_rating: float | None = Field(default=None, ge=0.0, le=10.0)

    # Audience scores
    audience_score: int | None = Field(default=None, ge=0, le=100)
    audience_state: str | None = Field(default=None, max_length=20)
    audience_count: int = Field(default=0, ge=0)
    audience_average_rating: float | None = Field(default=None, ge=0.0, le=5.0)

    # RAG content
    critics_consensus: str | None = Field(default=None, max_length=2000)

    # Metadata
    rt_url: str | None = Field(default=None, max_length=500)
    rt_rating: str | None = Field(default=None, max_length=20)

    @property
    def is_certified_fresh(self) -> bool:
        """Check if film has Certified Fresh status."""
        return self.tomatometer_state == "certified_fresh"

    @property
    def has_scores(self) -> bool:
        """Check if any score is available."""
        return self.tomatometer_score is not None or self.audience_score is not None


class IMDBFilmData(BaseModel):
    """Film data from IMDB SQLite extraction.

    Attributes:
        imdb_id: IMDb identifier (primary key).
        tmdb_id: TMDB ID if available for joining.
        title: Film title from IMDB.
        year: Release year.
        runtime: Duration in minutes.
        imdb_rating: IMDB average rating (0-10).
        imdb_votes: Number of IMDB votes.
        genres: Comma-separated genres.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    # Identifiers
    imdb_id: str = Field(pattern=IMDB_ID_PATTERN)
    tmdb_id: int | None = Field(default=None, gt=0)

    # Basic info
    title: str = Field(min_length=1, max_length=500)
    year: int | None = Field(default=None, ge=1888, le=2030)
    runtime: int | None = Field(default=None, ge=1, le=1000)

    # IMDB metrics
    imdb_rating: float | None = Field(default=None, ge=0.0, le=10.0)
    imdb_votes: int = Field(default=0, ge=0)

    # Genres as string (IMDB format)
    genres: str | None = Field(default=None, max_length=255)

    @property
    def genres_list(self) -> list[str]:
        """Parse genres string to list."""
        if not self.genres:
            return []
        return [g.strip() for g in self.genres.split(",") if g.strip()]


class KaggleFilmData(BaseModel):
    """Film data from Kaggle CSV extraction.

    Attributes:
        tmdb_id: TMDB ID if present in CSV.
        imdb_id: IMDB ID if present.
        title: Film title.
        year: Release year.
        rating: Kaggle dataset rating.
        votes: Number of votes.
        overview: Plot description.
        genres: List of genres.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    # Identifiers (at least one required)
    tmdb_id: int | None = Field(default=None, gt=0)
    imdb_id: str | None = Field(default=None, pattern=IMDB_ID_PATTERN)

    # Basic info
    title: str = Field(min_length=1, max_length=500)
    year: int | None = Field(default=None, ge=1888, le=2030)
    runtime: int | None = Field(default=None, ge=1, le=1000)

    # Metrics
    rating: float | None = Field(default=None, ge=0.0, le=10.0)
    votes: int = Field(default=0, ge=0)

    # Content
    overview: str | None = Field(default=None, max_length=5000)
    genres: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_has_identifier(self) -> Self:
        """Ensure at least one identifier is present."""
        if self.tmdb_id is None and self.imdb_id is None:
            raise ValueError("At least tmdb_id or imdb_id required")
        return self


class SparkFilmData(BaseModel):
    """Film data from Spark Big Data extraction.

    Attributes:
        tmdb_id: TMDB ID for joining.
        imdb_id: IMDB ID if available.
        title: Film title.
        year: Release year.
        rating: Aggregated rating from Spark.
        votes: Vote count.
        budget: Budget if available.
        revenue: Revenue if available.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    # Identifiers
    tmdb_id: int | None = Field(default=None, gt=0)
    imdb_id: str | None = Field(default=None, pattern=IMDB_ID_PATTERN)

    # Basic info
    title: str = Field(min_length=1, max_length=500)
    year: int | None = Field(default=None, ge=1888, le=2030)

    # Metrics
    rating: float | None = Field(default=None, ge=0.0, le=10.0)
    votes: int = Field(default=0, ge=0)

    # Financial (Spark aggregated)
    budget: int = Field(default=0, ge=0)
    revenue: int = Field(default=0, ge=0)


# =============================================================================
# AGGREGATED OUTPUT SCHEMA
# =============================================================================


class AggregatedFilm(BaseModel):
    """Unified film data after multi-source aggregation.

    Contains merged data from all sources with computed
    aggregated score for RAG ranking.

    Attributes:
        tmdb_id: Primary identifier.
        imdb_id: Secondary identifier.
        title: Canonical title (TMDB priority).
        aggregated_score: Weighted score from all sources.
        sources: List of sources that contributed data.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    # ==========================================================================
    # Identifiers
    # ==========================================================================
    tmdb_id: int = Field(gt=0)
    imdb_id: str | None = Field(default=None, pattern=IMDB_ID_PATTERN)

    # ==========================================================================
    # Basic Information (TMDB primary)
    # ==========================================================================
    title: str = Field(min_length=1, max_length=500)
    original_title: str | None = Field(default=None, max_length=500)
    release_date: date | None = None
    tagline: str | None = Field(default=None, max_length=500)
    runtime: int | None = Field(default=None, ge=1, le=1000)
    original_language: str | None = Field(default=None, max_length=10)
    adult: bool = Field(default=False)
    status: str = Field(default="Released", max_length=50)

    # ==========================================================================
    # RAG Content (prioritized sources)
    # ==========================================================================
    overview: str | None = Field(default=None, max_length=5000)
    critics_consensus: str | None = Field(default=None, max_length=2000)

    # ==========================================================================
    # TMDB Metrics
    # ==========================================================================
    popularity: float = Field(default=0.0, ge=0.0)
    vote_average: float = Field(default=0.0, ge=0.0, le=10.0)
    vote_count: int = Field(default=0, ge=0)

    # ==========================================================================
    # Rotten Tomatoes Metrics
    # ==========================================================================
    tomatometer_score: int | None = Field(default=None, ge=0, le=100)
    tomatometer_state: str | None = Field(default=None, max_length=20)
    audience_score: int | None = Field(default=None, ge=0, le=100)
    critics_count: int = Field(default=0, ge=0)
    audience_count: int = Field(default=0, ge=0)
    rt_url: str | None = Field(default=None, max_length=500)

    # ==========================================================================
    # IMDB Metrics
    # ==========================================================================
    imdb_rating: float | None = Field(default=None, ge=0.0, le=10.0)
    imdb_votes: int = Field(default=0, ge=0)

    # ==========================================================================
    # Kaggle/Spark Metrics
    # ==========================================================================
    kaggle_rating: float | None = Field(default=None, ge=0.0, le=10.0)
    spark_rating: float | None = Field(default=None, ge=0.0, le=10.0)

    # ==========================================================================
    # Financial Data
    # ==========================================================================
    budget: int = Field(default=0, ge=0)
    revenue: int = Field(default=0, ge=0)

    # ==========================================================================
    # Media URLs
    # ==========================================================================
    poster_path: str | None = Field(default=None, max_length=255)
    backdrop_path: str | None = Field(default=None, max_length=255)
    homepage: str | None = None

    # ==========================================================================
    # Relations (denormalized)
    # ==========================================================================
    genres: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    # ==========================================================================
    # Aggregation Metadata
    # ==========================================================================
    aggregated_score: float = Field(default=0.0, ge=0.0, le=10.0)
    sources: list[str] = Field(default_factory=list)
    enrichment_count: int = Field(default=1, ge=1)

    @field_validator("sources", mode="before")
    @classmethod
    def ensure_list(cls, v: list[str] | str | None) -> list[str]:
        """Convert sources to list if string."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    @property
    def year(self) -> int | None:
        """Extract year from release date."""
        return self.release_date.year if self.release_date else None

    @property
    def is_certified_fresh(self) -> bool:
        """Check Certified Fresh status."""
        return self.tomatometer_state == "certified_fresh"

    @property
    def has_rt_data(self) -> bool:
        """Check if RT enrichment is present."""
        return "rt" in self.sources or "rotten_tomatoes" in self.sources

    @property
    def has_imdb_data(self) -> bool:
        """Check if IMDB enrichment is present."""
        return "imdb" in self.sources

    @property
    def roi(self) -> float | None:
        """Calculate return on investment."""
        if self.budget and self.budget > 0:
            return round(self.revenue / self.budget, 2)
        return None

    @property
    def rag_text(self) -> str:
        """Generate combined text for RAG embedding.

        Prioritizes critics_consensus over overview for
        semantic search quality.

        Returns:
            Combined text for embedding generation.
        """
        parts: list[str] = [self.title]
        if self.critics_consensus:
            parts.append(self.critics_consensus)
        if self.overview:
            parts.append(self.overview)
        if self.tagline:
            parts.append(self.tagline)
        return " ".join(parts)
