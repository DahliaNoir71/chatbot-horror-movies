"""Video model for YouTube video metadata.

Stores video information from YouTube Data API v3.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, ExtractedAtMixin


class Video(Base, ExtractedAtMixin):
    """YouTube video metadata.

    Attributes:
        id: Internal primary key.
        youtube_id: YouTube video identifier.
        title: Video title.
        description: Video description.
        channel_id: YouTube channel identifier.
        channel_title: Channel name.
        view_count: Number of views.
        like_count: Number of likes.
        comment_count: Number of comments.
        duration: Video duration (ISO 8601).
        published_at: Publication timestamp.
        thumbnail_url: Thumbnail image URL.
        video_type: Classification (review, analysis, etc.).
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

    __table_args__ = (Index("idx_videos_published", "published_at"),)

    @property
    def youtube_url(self) -> str:
        """Generate YouTube watch URL."""
        return f"https://www.youtube.com/watch?v={self.youtube_id}"

    def __repr__(self) -> str:
        """Return string representation."""
        title_preview = self.title[:30] if len(self.title) > 30 else self.title
        return f"<Video(id={self.id}, youtube_id='{self.youtube_id}', title='{title_preview}...')>"
