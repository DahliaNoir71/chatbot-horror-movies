"""YouTube video transcript repository.

Provides CRUD and query operations for video transcripts
used in RAG semantic search.
"""

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.youtube import VideoTranscript
from src.database.repositories.base import BaseRepository


class VideoTranscriptRepository(BaseRepository[VideoTranscript]):
    """Repository for VideoTranscript entity operations.

    Transcripts are text extracted from YouTube videos
    for RAG semantic search.
    """

    model = VideoTranscript

    def __init__(self, session: Session) -> None:
        """Initialize transcript repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_video_id(self, video_id: int) -> VideoTranscript | None:
        """Retrieve transcript by video ID.

        Args:
            video_id: Video primary key.

        Returns:
            VideoTranscript instance or None.
        """
        return self.get_by_field("video_id", video_id)

    def get_by_video_and_language(
        self,
        video_id: int,
        language: str,
    ) -> VideoTranscript | None:
        """Retrieve transcript by video ID and language.

        Args:
            video_id: Video primary key.
            language: ISO 639-1 language code.

        Returns:
            VideoTranscript instance or None.
        """
        stmt = select(VideoTranscript).where(
            VideoTranscript.video_id == video_id,
            VideoTranscript.language == language,
        )
        return self._session.scalars(stmt).first()

    def get_by_language(self, language: str, limit: int = 100) -> list[VideoTranscript]:
        """Get transcripts in a specific language.

        Args:
            language: ISO 639-1 language code.
            limit: Maximum results.

        Returns:
            List of transcripts in that language.
        """
        stmt = select(VideoTranscript).where(VideoTranscript.language == language).limit(limit)
        return list(self._session.scalars(stmt).all())

    def get_video_ids_with_transcripts(self) -> set[int]:
        """Get all video IDs that have transcripts.

        Returns:
            Set of video IDs.
        """
        stmt = select(VideoTranscript.video_id)
        return set(self._session.scalars(stmt).all())

    def upsert(self, data: dict[str, Any]) -> VideoTranscript:
        """Insert or update transcript.

        Args:
            data: Transcript data with video_id.

        Returns:
            Upserted transcript instance.
        """
        stmt = (
            insert(VideoTranscript)
            .values(**data)
            .on_conflict_do_update(
                index_elements=["video_id", "language"],
                set_={k: v for k, v in data.items() if k not in ("video_id", "language")},
            )
            .returning(VideoTranscript)
        )
        result = self._session.execute(stmt)
        self._session.flush()
        return result.scalar_one()

    def bulk_upsert(self, transcripts_data: list[dict[str, Any]]) -> int:
        """Bulk insert or update transcripts.

        Args:
            transcripts_data: List of transcript dictionaries.

        Returns:
            Number of transcripts processed.
        """
        if not transcripts_data:
            return 0

        stmt = insert(VideoTranscript).values(transcripts_data)
        update_cols = {
            col.name: col for col in stmt.excluded if col.name not in ("id", "video_id", "language")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["video_id", "language"],
            set_=update_cols,
        )
        self._session.execute(stmt)
        self._session.flush()
        return len(transcripts_data)

    def update_word_count(self, transcript_id: int, word_count: int) -> None:
        """Update transcript word count.

        Args:
            transcript_id: Transcript primary key.
            word_count: Number of words in transcript.
        """
        stmt = (
            update(VideoTranscript)
            .where(VideoTranscript.id == transcript_id)
            .values(word_count=word_count)
        )
        self._session.execute(stmt)
        self._session.flush()
