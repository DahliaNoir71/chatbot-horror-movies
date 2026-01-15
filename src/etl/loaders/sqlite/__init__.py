"""SQLite loaders package.

Provides loaders for SQLite data sources
including IMDB dataset enrichment.
"""

from src.etl.loaders.sqlite.loader import IMDBLoader

__all__ = ["IMDBLoader"]
