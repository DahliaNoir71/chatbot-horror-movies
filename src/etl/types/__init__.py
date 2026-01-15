"""ETL data types package.

Exports all TypedDict definitions for raw and normalized
data structures used throughout the ETL pipeline.

Usage:
    from src.etl.types import TMDBFilmData, NormalizedFilmData
"""

from src.etl.types.kaggle import (
    KaggleEnrichmentStats,
    KaggleExtractionResult,
    KaggleHorrorMovieNormalized,
    KaggleHorrorMovieRaw,
)
from src.etl.types.normalized import (
    NormalizedCompanyData,
    NormalizedCreditData,
    NormalizedFilmData,
    NormalizedGenreData,
    NormalizedKeywordData,
    NormalizedLanguageData,
    NormalizedRTScoreData,
)
from src.etl.types.pipeline import (
    CreditLoadInput,
    ETLCheckpoint,
    ETLPipelineStats,
    ETLProgress,
    ETLResult,
    ETLRunConfig,
    ExtractionStats,
    FilmMatchCandidate,
    FilmMatchResult,
    FilmToEnrich,
    LoadStats,
    TransformationStats,
)
from src.etl.types.rotten_tomatoes import (
    RTMoviePageData,
    RTScoreData,
    RTSearchResult,
)
from src.etl.types.tmdb import (
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
    "CreditLoadInput",
    "FilmToEnrich",
]
