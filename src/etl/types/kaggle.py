"""Kaggle and Spark data types.

TypedDict definitions for data structures from Kaggle
TMDB dataset processed via Apache Spark.
"""

from typing import NotRequired, TypedDict

from src.etl.types.tmdb import (
    TMDBKeywordData,
    TMDBProductionCompanyData,
    TMDBSpokenLanguageData,
)


class KaggleMovieData(TypedDict):
    """Movie data from Kaggle TMDB dataset (processed via Spark).

    The Kaggle dataset contains denormalized JSON strings
    for nested fields like genres, keywords, etc.
    """

    # Identifiers
    id: int
    imdb_id: NotRequired[str | None]

    # Financial data (main enrichment purpose)
    budget: int
    revenue: int

    # Additional metadata
    original_language: NotRequired[str | None]
    original_title: NotRequired[str | None]
    runtime: NotRequired[int | None]
    status: NotRequired[str | None]
    release_date: NotRequired[str | None]

    # Nested JSON fields (as strings in CSV)
    genres: NotRequired[str | None]
    keywords: NotRequired[str | None]
    production_companies: NotRequired[str | None]
    spoken_languages: NotRequired[str | None]
    production_countries: NotRequired[str | None]


class KaggleCreditsData(TypedDict):
    """Credits data from Kaggle credits.csv file."""

    # Movie identifier
    id: int

    # JSON strings
    cast: str
    crew: str


class SparkEnrichmentData(TypedDict):
    """Enrichment data output from Spark processing.

    Parsed and normalized data ready for database enrichment.
    """

    tmdb_id: int
    budget: NotRequired[int]
    revenue: NotRequired[int]
    production_companies: NotRequired[list[TMDBProductionCompanyData]]
    spoken_languages: NotRequired[list[TMDBSpokenLanguageData]]
    keywords: NotRequired[list[TMDBKeywordData]]


class SparkProcessingResult(TypedDict):
    """Result of Spark batch processing."""

    total_processed: int
    enriched_count: int
    skipped_count: int
    error_count: int
    duration_seconds: float


class KaggleDatasetInfo(TypedDict):
    """Kaggle dataset metadata."""

    dataset_name: str
    file_path: str
    row_count: int
    columns: list[str]
    size_mb: float
