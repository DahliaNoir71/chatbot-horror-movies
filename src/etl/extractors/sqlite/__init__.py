"""SQLite extractors package.

Provides extractors for SQLite database sources
including IMDB dataset.
"""

from src.etl.extractors.sqlite.extractor import SQLiteExtractor
from src.etl.extractors.sqlite.normalizer import IMDBNormalizer
from src.etl.extractors.sqlite.queries import IMDBQueries

__all__ = ["SQLiteExtractor", "IMDBNormalizer", "IMDBQueries"]
