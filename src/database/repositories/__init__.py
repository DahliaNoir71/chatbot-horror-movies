"""Database repositories for HorrorBot.

Provides repository pattern implementations for all
database entities with CRUD and specialized queries.

Usage:
    from src.database.repositories import FilmRepository, GenreRepository
    from src.database import get_database

    db = get_database()
    with db.session() as session:
        film_repo = FilmRepository(session)
        films = film_repo.search_by_title("Halloween")
"""

# Audit repositories
from src.database.repositories.audit import (
    DataRetentionLogRepository,
    ETLErrorData,
    ETLRunRepository,
    ETLStatsData,
    RetentionDetailsData,
)
from src.database.repositories.base import BaseRepository

# Rotten Tomatoes repositories
from src.database.repositories.rotten_tomatoes import RTScoreRepository

# TMDB repositories
from src.database.repositories.tmdb import (
    CreditData,
    CreditRepository,
    FilmRepository,
    GenreRepository,
    KeywordRepository,
    ProductionCompanyData,
    ProductionCompanyRepository,
    SpokenLanguageData,
    SpokenLanguageRepository,
)

# YouTube repositories
from src.database.repositories.youtube import (
    FilmVideoRepository,
    VideoRepository,
    VideoTranscriptRepository,
)

__all__ = [
    # Base
    "BaseRepository",
    # TMDB
    "FilmRepository",
    "GenreRepository",
    "KeywordRepository",
    "CreditRepository",
    "CreditData",
    "ProductionCompanyRepository",
    "ProductionCompanyData",
    "SpokenLanguageRepository",
    "SpokenLanguageData",
    # Rotten Tomatoes
    "RTScoreRepository",
    # YouTube
    "VideoRepository",
    "VideoTranscriptRepository",
    "FilmVideoRepository",
    # Audit
    "ETLRunRepository",
    "ETLErrorData",
    "ETLStatsData",
    "DataRetentionLogRepository",
    "RetentionDetailsData",
]
