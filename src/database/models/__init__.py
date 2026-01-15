"""Database models package.

Re-exports all models organized by source:
- tmdb: TMDB API models (films, genres, credits, etc.)
- rotten_tomatoes: RT scraped data (scores, consensus)
- audit: RGPD compliance and ETL tracking
"""

# Audit models
from src.database.models.audit import (
    DataRetentionLog,
    ETLRun,
    RGPDProcessingRegistry,
)
from src.database.models.base import Base, ExtractedAtMixin

# Rotten Tomatoes models
from src.database.models.rotten_tomatoes import RTScore

# TMDB models
from src.database.models.tmdb import (
    Credit,
    Film,
    FilmCompany,
    FilmGenre,
    FilmKeyword,
    FilmLanguage,
    Genre,
    Keyword,
    ProductionCompany,
    SpokenLanguage,
)

__all__ = [
    # Base
    "Base",
    "ExtractedAtMixin",
    # TMDB
    "Film",
    "Genre",
    "Keyword",
    "Credit",
    "ProductionCompany",
    "SpokenLanguage",
    "FilmGenre",
    "FilmKeyword",
    "FilmCompany",
    "FilmLanguage",
    # Rotten Tomatoes
    "RTScore",
    # Audit
    "RGPDProcessingRegistry",
    "DataRetentionLog",
    "ETLRun",
]
