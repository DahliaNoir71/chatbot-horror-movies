"""SQLAlchemy ORM models for HorrorBot database.

This module exports all database models and the Base class
for use throughout the application.

Usage:
    from src.database.models import Base, Film, Genre, RTScore

Tables:
    - films: Main film data (TMDB)
    - genres: Film genres
    - film_genres: Film-Genre association
    - keywords: Semantic keywords
    - film_keywords: Film-Keyword association
    - credits: Directors, actors, etc.
    - rt_scores: Rotten Tomatoes data
    - videos: YouTube videos
    - video_transcripts: Video transcripts for RAG
    - film_videos: Film-Video association with match score
    - production_companies: Film studios
    - film_companies: Film-Company association
    - spoken_languages: Language reference
    - film_languages: Film-Language association
    - rgpd_processing_registry: GDPR Article 30 compliance
    - data_retention_log: Data retention audit
    - etl_runs: Pipeline execution tracking
"""

from src.database.models.audit import (
    DataRetentionLog,
    ETLRun,
    RGPDProcessingRegistry,
)
from src.database.models.base import Base, ExtractedAtMixin, TimestampMixin
from src.database.models.film import (
    Credit,
    Film,
    FilmGenre,
    FilmKeyword,
    Genre,
    Keyword,
)
from src.database.models.production import (
    FilmCompany,
    FilmLanguage,
    ProductionCompany,
    SpokenLanguage,
)
from src.database.models.rotten_tomatoes import RTScore
from src.database.models.youtube import FilmVideo, Video, VideoTranscript

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "ExtractedAtMixin",
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
]
