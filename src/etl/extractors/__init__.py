"""ETL extractors package.

Provides data extraction from multiple sources:
- TMDB: Horror film metadata
- Rotten Tomatoes: Critics scores (to be implemented)
- YouTube: Video content (to be implemented)
- Kaggle/Spark: Dataset processing (to be implemented)

Classes:
    BaseExtractor: Abstract base for all extractors.
    TMDBExtractor: TMDB API extractor.
"""

from src.etl.extractors.base import BaseExtractor
from src.etl.extractors.tmdb import (
    TMDBClient,
    TMDBClientError,
    TMDBExtractor,
    TMDBNormalizer,
    TMDBNotFoundError,
    TMDBRateLimitError,
)

__all__ = [
    # Base
    "BaseExtractor",
    # TMDB
    "TMDBExtractor",
    "TMDBClient",
    "TMDBNormalizer",
    "TMDBClientError",
    "TMDBRateLimitError",
    "TMDBNotFoundError",
]
