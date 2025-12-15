"""Modèles SQLAlchemy pour PostgreSQL."""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    Column,
    Date,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Film(Base):
    """Modèle film avec embedding pgvector."""

    __tablename__ = "films"

    id = Column(Integer, primary_key=True)
    tmdb_id = Column(Integer, unique=True, nullable=False, index=True)
    imdb_id = Column(String(10), nullable=True)

    title = Column(String(500), nullable=False)
    original_title = Column(String(500), nullable=True)
    year = Column(Integer, nullable=False, index=True)
    release_date = Column(Date, nullable=True)

    # Scores
    vote_average = Column(Float, nullable=True)
    vote_count = Column(Integer, default=0)
    popularity = Column(Float, default=0.0)

    tomatometer_score = Column(Integer, nullable=True, index=True)
    audience_score = Column(Integer, nullable=True)
    certified_fresh = Column(Boolean, default=False)

    # Textes
    critics_consensus = Column(Text, nullable=True)
    overview = Column(Text, nullable=True)
    tagline = Column(String(500), nullable=True)

    # Métadonnées
    runtime = Column(Integer, nullable=True)
    original_language = Column(String(2), nullable=True)
    genres = Column(JSON, nullable=True)

    # URLs
    rotten_tomatoes_url = Column(Text, nullable=True)
    poster_path = Column(String(255), nullable=True)
    backdrop_path = Column(String(255), nullable=True)

    # Embedding vectoriel (384 dimensions)
    embedding = Column(Vector(384), nullable=True)

    # Audit
    created_at = Column(TIMESTAMP, default=datetime.now)
    updated_at = Column(TIMESTAMP, default=datetime.now, onupdate=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "id": self.id,
            "tmdb_id": self.tmdb_id,
            "title": self.title,
            "year": self.year,
            "tomatometer_score": self.tomatometer_score,
            "overview": self.overview or self.critics_consensus,
        }
