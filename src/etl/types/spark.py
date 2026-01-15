"""Spark extraction type definitions.

TypedDict definitions for Big Data processing with PySpark.
"""

from typing import TypedDict


class SparkRawMovie(TypedDict, total=False):
    """Raw movie data from Spark DataFrame.

    Matches Kaggle horror_movies.csv schema after Spark inference.
    All fields optional (total=False) for partial data handling.
    """

    id: int
    title: str
    original_title: str
    release_date: str
    vote_average: float
    vote_count: int
    popularity: float
    overview: str
    genre_names: str
    original_language: str
    budget: int
    revenue: int
    runtime: int
    status: str
    tagline: str
    poster_path: str
    backdrop_path: str


class SparkEnrichedMovie(TypedDict, total=False):
    """Enriched movie data after SparkSQL processing.

    Contains computed fields from analytical queries.
    """

    kaggle_id: int
    title: str
    release_date: str
    release_year: int
    decade: int
    rating: float
    votes: int
    popularity: float
    original_language: str
    runtime: int
    overview: str
    genre_names: str
    budget: int
    revenue: int
    rating_category: str
    global_rank: int


class SparkNormalized(TypedDict):
    """Normalized Spark data for aggregation.

    Ready for merge with other sources.
    All required fields for database insertion.
    """

    kaggle_id: int
    title: str
    release_year: int | None
    decade: int | None
    rating: float
    votes: int
    popularity: float
    runtime: int | None
    overview: str | None
    genre_names: str | None
    rating_category: str
    source: str


class SparkDecadeStats(TypedDict):
    """Decade-level aggregate statistics."""

    decade: int
    movie_count: int
    avg_rating: float
    avg_votes: float
    avg_popularity: float
    min_rating: float
    max_rating: float


class SparkLanguageStats(TypedDict):
    """Language-level aggregate statistics."""

    original_language: str
    movie_count: int
    avg_rating: float
    high_rated_count: int
    high_rated_pct: float


class SparkRankedMovie(TypedDict):
    """Movie with ranking information."""

    id: int
    title: str
    release_year: int
    rating: float
    votes: int
    year_rank: int


class SparkPercentileMovie(TypedDict):
    """Movie with percentile information."""

    id: int
    title: str
    rating: float
    votes: int
    percentile: float
    quartile: int


class SparkExtractionResult(TypedDict):
    """Spark extraction statistics."""

    total_rows: int
    filtered_movies: int
    exported_count: int
    duration_seconds: float
    export_path: str | None
