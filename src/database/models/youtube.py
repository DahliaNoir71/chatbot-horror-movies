"""YouTube SQLAlchemy models.

Contains Video, VideoTranscript, and FilmVideo models
for storing YouTube video data and film associations.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, ExtractedAtMixin

if TYPE_CHECKING:
    from src.database.models.film import Film


class Video(Base, ExtractedAtMixin):
    """YouTube video metadata.

    Stores video information from YouTube Data API v3,
    including metrics and channel information.

    Attributes:
        id: Internal primary key.
        youtube_id: YouTube video identifier.
        title: Video title.
        channel_title: Channel name.
        view_count: Number of views.
    """

    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    youtube_id: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Channel info
    channel_id: Mapped[str | None] = mapped_column(String(50), index=True)
    channel_title: Mapped[str | None] = mapped_column(String(255))

    # Metrics
    view_count: Mapped[int] = mapped_column(BigInteger, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    duration: Mapped[str | None] = mapped_column(String(50))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))

    # Video classification
    video_type: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    transcript: Mapped["VideoTranscript | None"] = relationship(
        "VideoTranscript",
        back_populates="video",
        uselist=False,
        cascade="all, delete-orphan",
    )
    films: Mapped[list["Film"]] = relationship(
        "Film",
        secondary="film_videos",
        back_populates="videos",
    )

    # Indexes
    __table_args__ = (
        Index("idx_videos_published", "published_at"),
        Index("idx_videos_title_trgm", "title", postgresql_using="gin"),
    )

    @property
    def youtube_url(self) -> str:
        """Generate YouTube watch URL."""
        return f"https://www.youtube.com/watch?v={self.youtube_id}"

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<Video(id={self.id}, youtube_id='{self.youtube_id}', title='{self.title[:30]}...')>"
        )


class VideoTranscript(Base, ExtractedAtMixin):
    """YouTube video transcript.

    Stores the full transcript text and embedding
    for RAG semantic search.

    Attributes:
        id: Primary key.
        video_id: Foreign key to videos (1:1).
        transcript: Full transcript text.
        language: Transcript language code.
        embedding: Vector embedding for RAG.
    """

    __tablename__ = "video_transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Content
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    is_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    # Word count
    word_count: Mapped[int | None] = mapped_column(Integer)

    # Vector embedding for RAG
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="transcript")

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<VideoTranscript(video_id={self.video_id}, words={self.word_count})>"


class FilmVideo(Base):
    """Association table for Film-Video with match score.

    Stores the relationship between films and YouTube videos,
    including the confidence score of the matching algorithm.

    Attributes:
        id: Primary key.
        film_id: Foreign key to films.
        video_id: Foreign key to videos.
        match_score: Confidence score (0-1).
        match_method: Method used for matching.
    """

    __tablename__ = "film_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("films.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Match quality
    match_score: Mapped[float] = mapped_column(
        Numeric(4, 3),
        nullable=False,
    )
    match_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Metadata
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "match_score >= 0 AND match_score <= 1",
            name="chk_match_score",
        ),
        Index("idx_film_videos_score", "match_score"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<FilmVideo(film_id={self.film_id}, "
            f"video_id={self.video_id}, "
            f"score={self.match_score})>"
        )
