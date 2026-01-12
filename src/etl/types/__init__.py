"""ETL data types package.

Exports all TypedDict definitions for raw and normalized
data structures used throughout the ETL pipeline.

Usage:
    from src.etl.types import TMDBFilmData, NormalizedFilmData
"""

from src.etl.types.kaggle import (
    KaggleCreditsData,
    KaggleDatasetInfo,
    KaggleMovieData,
    SparkEnrichmentData,
    SparkProcessingResult,
)
from src.etl.types.normalized import (
    NormalizedCompanyData,
    NormalizedCreditData,
    NormalizedFilmData,
    NormalizedGenreData,
    NormalizedKeywordData,
    NormalizedLanguageData,
    NormalizedRTScoreData,
    NormalizedTranscriptData,
    NormalizedVideoData,
)
from src.etl.types.pipeline import (
    ETLCheckpoint,
    ETLPipelineStats,
    ETLProgress,
    ETLResult,
    ETLRunConfig,
    ExtractionStats,
    FilmMatchCandidate,
    FilmMatchResult,
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
from src.etl.types.youtube import (
    YouTubeChannelData,
    YouTubePlaylistData,
    YouTubePlaylistItemData,
    YouTubeSearchResultData,
    YouTubeTranscriptData,
    YouTubeTranscriptSegment,
    YouTubeVideoData,
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
    # YouTube
    "YouTubeVideoData",
    "YouTubeTranscriptData",
    "YouTubeTranscriptSegment",
    "YouTubeChannelData",
    "YouTubePlaylistData",
    "YouTubePlaylistItemData",
    "YouTubeSearchResultData",
    # Kaggle/Spark
    "KaggleMovieData",
    "KaggleCreditsData",
    "KaggleDatasetInfo",
    "SparkEnrichmentData",
    "SparkProcessingResult",
    # Normalized
    "NormalizedFilmData",
    "NormalizedCreditData",
    "NormalizedGenreData",
    "NormalizedKeywordData",
    "NormalizedVideoData",
    "NormalizedTranscriptData",
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
