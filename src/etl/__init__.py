"""ETL pipeline package for HorrorBot.

Provides data extraction, transformation, and loading
from multiple sources: TMDB, Rotten Tomatoes, Kaggle/Spark, PostgreSQL.

Modules:
    types: TypedDict definitions for raw and normalized data
    extractors: Source-specific data extraction classes
    transformers: Data normalization and cleaning
    loaders: Database insertion logic
"""

from src.etl.types import (
    # Pipeline
    ETLCheckpoint,
    ETLPipelineStats,
    ETLProgress,
    ETLResult,
    ETLRunConfig,
    ExtractionStats,
    FilmMatchCandidate,
    FilmMatchResult,
    # Kaggle
    KaggleEnrichmentStats,
    KaggleExtractionResult,
    KaggleHorrorMovieNormalized,
    KaggleHorrorMovieRaw,
    LoadStats,
    # Normalized
    NormalizedCompanyData,
    NormalizedCreditData,
    NormalizedFilmData,
    NormalizedGenreData,
    NormalizedKeywordData,
    NormalizedLanguageData,
    NormalizedRTScoreData,
    # Rotten Tomatoes
    RTMoviePageData,
    RTScoreData,
    RTSearchResult,
    # TMDB
    TMDBCastData,
    TMDBCreditsData,
    TMDBCrewData,
    TMDBDiscoverResponse,
    TMDBFilmData,
    TMDBGenreData,
    TMDBKeywordData,
    TMDBKeywordsResponse,
    TMDBProductionCompanyData,
    TMDBSpokenLanguageData,
    TransformationStats,
)

__all__ = [
    # TMDB
    "TMDBFilmData",
    "TMDBGenreData",
    "TMDBKeywordData",
    "TMDBCastData",
    "TMDBCrewData",
    "TMDBCreditsData",
    "TMDBProductionCompanyData",
    "TMDBSpokenLanguageData",
    "TMDBDiscoverResponse",
    "TMDBKeywordsResponse",
    # Rotten Tomatoes
    "RTScoreData",
    "RTSearchResult",
    "RTMoviePageData",
    # Kaggle
    "KaggleHorrorMovieRaw",
    "KaggleHorrorMovieNormalized",
    "KaggleExtractionResult",
    "KaggleEnrichmentStats",
    # Normalized
    "NormalizedFilmData",
    "NormalizedCreditData",
    "NormalizedGenreData",
    "NormalizedKeywordData",
    "NormalizedRTScoreData",
    "NormalizedCompanyData",
    "NormalizedLanguageData",
    # Pipeline
    "ETLResult",
    "ETLCheckpoint",
    "ETLRunConfig",
    "ETLProgress",
    "ETLPipelineStats",
    "ExtractionStats",
    "TransformationStats",
    "LoadStats",
    "FilmMatchResult",
    "FilmMatchCandidate",
]
