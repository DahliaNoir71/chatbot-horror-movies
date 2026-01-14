"""FilmVideo association model.

Links films to related YouTube videos with match metadata.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class FilmVideo(Base):
    """Association between films and YouTube videos.

    Attributes:
        film_id: Foreign key to films.
        video_id: Foreign key to videos.
        match_score: Similarity score (0.0-1.0).
        match_method: Algorithm used for matching.
        matched_at: Timestamp of match creation.
    """

    __tablename__ = "film_videos"

    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("films.id", ondelete="CASCADE"),
        primary_key=True,
    )
    video_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Match metadata
    match_score: Mapped[float] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        default=1.0,
    )
    match_method: Mapped[str] = mapped_column(
        String(50),
        default="title_similarity",
    )

    # Timestamps
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("idx_film_videos_score", "match_score"),)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<FilmVideo(film_id={self.film_id}, "
            f"video_id={self.video_id}, score={self.match_score})>"
        )
