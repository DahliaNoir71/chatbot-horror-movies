"""TMDB extractor package.

Provides extraction of horror films from The Movie Database API.

Classes:
    TMDBExtractor: Main extractor orchestrating the process.
    TMDBClient: HTTP client with rate limiting.
    TMDBNormalizer: Data transformation to normalized format.

Exceptions:
    TMDBClientError: Base client error.
    TMDBRateLimitError: Rate limit exceeded.
    TMDBNotFoundError: Resource not found.

Usage:
    from src.etl.extractors.tmdb import TMDBExtractor

    extractor = TMDBExtractor()
    result = extractor.extract(year_min=2020, year_max=2024)
"""

from src.etl.extractors.tmdb.client import (
    TMDBClient,
    TMDBClientError,
    TMDBNotFoundError,
    TMDBRateLimitError,
)
from src.etl.extractors.tmdb.normalizer import TMDBNormalizer
from src.etl.extractors.tmdb.tmdb import TMDBExtractor

__all__ = [
    "TMDBExtractor",
    "TMDBClient",
    "TMDBNormalizer",
    "TMDBClientError",
    "TMDBRateLimitError",
    "TMDBNotFoundError",
]
