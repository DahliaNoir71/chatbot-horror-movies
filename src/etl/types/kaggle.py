"""Kaggle horror movies data types.

TypedDict definitions for data structures from Kaggle
evangower/horror-movies dataset (TidyTuesday TMDB subset).
"""

from typing import NotRequired, TypedDict


class KaggleHorrorMovieRaw(TypedDict):
    """Raw movie data from Kaggle horror_movies.csv.

    Dataset: evangower/horror-movies (TidyTuesday)
    Source: TMDB filtered for Horror genre.

    Attributes:
        id: TMDB movie ID.
        title: Movie title.
        original_title: Original title.
        original_language: ISO 639-1 language code.
        overview: Movie synopsis.
        tagline: Marketing tagline.
        release_date: Release date (YYYY-MM-DD).
        poster_path: TMDB poster path.
        backdrop_path: TMDB backdrop path.
        popularity: TMDB popularity score.
        vote_average: Average rating (0-10).
        vote_count: Number of votes.
        budget: Production budget (USD).
        revenue: Box office revenue (USD).
        runtime: Duration in minutes.
        status: Release status (Released, etc.).
        adult: Adult content flag.
        genre_names: Comma-separated genre names.
        collection_name: Franchise/saga name.
    """

    id: int
    title: NotRequired[str | None]
    original_title: NotRequired[str | None]
    original_language: NotRequired[str | None]
    overview: NotRequired[str | None]
    tagline: NotRequired[str | None]
    release_date: NotRequired[str | None]
    poster_path: NotRequired[str | None]
    backdrop_path: NotRequired[str | None]
    popularity: NotRequired[float | None]
    vote_average: NotRequired[float | None]
    vote_count: NotRequired[int | None]
    budget: NotRequired[int | None]
    revenue: NotRequired[int | None]
    runtime: NotRequired[int | None]
    status: NotRequired[str | None]
    adult: NotRequired[bool | None]
    genre_names: NotRequired[str | None]
    collection_name: NotRequired[str | None]


class KaggleHorrorMovieNormalized(TypedDict):
    """Normalized Kaggle movie data for database insertion.

    Transformed from KaggleHorrorMovieRaw with validated
    and cleaned fields ready for upsert into films table.

    Attributes:
        tmdb_id: TMDB movie ID (mapped from 'id').
        title: Movie title (required).
        original_title: Original title.
        original_language: ISO 639-1 code.
        overview: Synopsis text.
        tagline: Marketing tagline.
        release_date: Parsed date object.
        poster_path: TMDB poster path.
        backdrop_path: TMDB backdrop path.
        popularity: Popularity score.
        vote_average: Average rating.
        vote_count: Vote count.
        budget: Budget in USD.
        revenue: Revenue in USD.
        runtime: Duration in minutes.
        status: Release status.
        adult: Adult content flag.
        source: Data source identifier.
    """

    tmdb_id: int
    title: str
    original_title: str | None
    original_language: str | None
    overview: str | None
    tagline: str | None
    release_date: NotRequired[str | None]
    poster_path: str | None
    backdrop_path: str | None
    popularity: float
    vote_average: float
    vote_count: int
    budget: int
    revenue: int
    runtime: int | None
    status: str
    adult: bool
    source: str


class KaggleExtractionResult(TypedDict):
    """Result of Kaggle CSV extraction."""

    total_rows: int
    valid_rows: int
    skipped_rows: int
    error_count: int
    duration_seconds: float


class KaggleEnrichmentStats(TypedDict):
    """Statistics for Kaggle enrichment operation.

    Tracks how many existing films were enriched
    vs new films inserted from Kaggle data.
    """

    films_enriched: int
    films_inserted: int
    budget_updates: int
    revenue_updates: int
    skipped: int
    errors: int
