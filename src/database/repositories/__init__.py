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

from src.database.repositories.base import BaseRepository
from src.database.repositories.credit import CreditRepository
from src.database.repositories.etl import DataRetentionLogRepository, ETLRunRepository
from src.database.repositories.film import FilmRepository
from src.database.repositories.genre import GenreRepository
from src.database.repositories.keyword import KeywordRepository
from src.database.repositories.production import (
    ProductionCompanyRepository,
    SpokenLanguageRepository,
)
from src.database.repositories.rt_score import RTScoreRepository
from src.database.repositories.video import (
    FilmVideoRepository,
    VideoRepository,
    VideoTranscriptRepository,
)

__all__ = [
    # Base
    "BaseRepository",
    # Film-related
    "FilmRepository",
    "GenreRepository",
    "KeywordRepository",
    "CreditRepository",
    # External sources
    "RTScoreRepository",
    "VideoRepository",
    "VideoTranscriptRepository",
    "FilmVideoRepository",
    # Production
    "ProductionCompanyRepository",
    "SpokenLanguageRepository",
    # ETL & Audit
    "ETLRunRepository",
    "DataRetentionLogRepository",
]
