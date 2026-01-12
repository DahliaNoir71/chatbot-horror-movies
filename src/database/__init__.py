"""Database package for HorrorBot.

Provides database connection management, ORM models, and repositories.

Usage:
    from src.database import get_database, FilmRepository, Film

    db = get_database()
    with db.session() as session:
        repo = FilmRepository(session)
        films = repo.search_by_title("Halloween")
"""

from src.database.connection import (
    DatabaseConnection,
    close_database,
    get_async_session,
    get_database,
    get_session,
    init_database,
)
from src.database.models import (
    Base,
    Credit,
    DataRetentionLog,
    ETLRun,
    Film,
    FilmCompany,
    FilmGenre,
    FilmKeyword,
    FilmLanguage,
    FilmVideo,
    Genre,
    Keyword,
    ProductionCompany,
    RGPDProcessingRegistry,
    RTScore,
    SpokenLanguage,
    Video,
    VideoTranscript,
)
from src.database.repositories import (
    BaseRepository,
    CreditRepository,
    DataRetentionLogRepository,
    ETLRunRepository,
    FilmRepository,
    FilmVideoRepository,
    GenreRepository,
    KeywordRepository,
    ProductionCompanyRepository,
    RTScoreRepository,
    SpokenLanguageRepository,
    VideoRepository,
    VideoTranscriptRepository,
)

__all__ = [
    # Connection
    "DatabaseConnection",
    "get_database",
    "get_session",
    "get_async_session",
    "init_database",
    "close_database",
    # Base
    "Base",
    # Film models
    "Film",
    "Genre",
    "Keyword",
    "Credit",
    "FilmGenre",
    "FilmKeyword",
    # Rotten Tomatoes
    "RTScore",
    # YouTube
    "Video",
    "VideoTranscript",
    "FilmVideo",
    # Production
    "ProductionCompany",
    "SpokenLanguage",
    "FilmCompany",
    "FilmLanguage",
    # Audit
    "RGPDProcessingRegistry",
    "DataRetentionLog",
    "ETLRun",
    # Repositories
    "BaseRepository",
    "FilmRepository",
    "GenreRepository",
    "KeywordRepository",
    "CreditRepository",
    "RTScoreRepository",
    "VideoRepository",
    "VideoTranscriptRepository",
    "FilmVideoRepository",
    "ProductionCompanyRepository",
    "SpokenLanguageRepository",
    "ETLRunRepository",
    "DataRetentionLogRepository",
]
