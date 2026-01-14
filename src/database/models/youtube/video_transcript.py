"""VideoTranscript model for YouTube transcripts.

Stores transcript text extracted from videos for RAG processing.
"""

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, ExtractedAtMixin


class VideoTranscript(Base, ExtractedAtMixin):
    """YouTube video transcript for RAG.

    Attributes:
        id: Internal primary key.
        video_id: Foreign key to videos.
        language: Transcript language (ISO 639-1).
        transcript_text: Full transcript content.
        is_auto_generated: Whether transcript is auto-generated.
        source: Transcript source (youtube_api, manual, etc.).
    """

    __tablename__ = "video_transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Transcript content
    language: Mapped[str] = mapped_column(String(10), default="en")
    transcript_text: Mapped[str | None] = mapped_column(Text)

    # Metadata
    is_auto_generated: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str] = mapped_column(String(50), default="youtube_api")

    # Stats
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("idx_transcripts_language", "language"),
        Index("idx_transcripts_video_lang", "video_id", "language", unique=True),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<VideoTranscript(video_id={self.video_id}, "
            f"language='{self.language}', words={self.word_count})>"
        )
