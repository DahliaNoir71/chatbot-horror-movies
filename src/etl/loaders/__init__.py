"""ETL loaders package.

Provides loaders for inserting extracted data into PostgreSQL.
Organized by extractor source.
"""

from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.loaders.tmdb import TMDBLoader

__all__ = [
    "BaseLoader",
    "LoaderStats",
    "TMDBLoader",
]
