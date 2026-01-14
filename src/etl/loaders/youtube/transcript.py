"""YouTube transcript data loader.

Handles transcript insertion with upsert on (video_id, language).
"""

from sqlalchemy.dialects.postgresql import insert

from src.database.models.youtube.video_transcript import VideoTranscript
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types import NormalizedTranscriptData


class TranscriptLoader(BaseLoader):
    """Loader for YouTube video transcripts.

    Uses (video_id, language) as unique constraint for upsert.
    """

    name = "youtube.transcript"

    def load(self, data: list[NormalizedTranscriptData]) -> LoaderStats:
        """Load transcripts into database.

        Args:
            data: List of normalized transcript data dictionaries.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        if not data:
            return self.stats

        total = len(data)
        self._logger.info(f"Loading {total} transcripts")

        for idx, transcript_data in enumerate(data, 1):
            self._upsert_transcript(transcript_data)
            self._log_progress(idx, total)

        self._session.flush()
        self._log_summary()
        return self.stats

    def _upsert_transcript(self, data: NormalizedTranscriptData) -> None:
        """Upsert a single transcript record.

        Args:
            data: Normalized transcript data dictionary.
        """
        video_id = data.get("video_id")
        if not video_id:
            self._record_error("Missing video_id in transcript data")
            return

        try:
            stmt = insert(VideoTranscript).values(**self._build_values(data))
            stmt = stmt.on_conflict_do_update(
                index_elements=["video_id", "language"],
                set_=self._build_update_set(stmt),
            )
            self._session.execute(stmt)
            self._record_insert()
        except Exception as e:
            self._record_error(f"Transcript for video {video_id} failed: {e}")

    @staticmethod
    def _build_values(data: NormalizedTranscriptData) -> dict[str, object]:
        """Build INSERT values from normalized data.

        Args:
            data: Normalized transcript data dictionary.

        Returns:
            Dictionary of column-value pairs for INSERT.
        """
        return {
            "video_id": data["video_id"],
            "language": data.get("language", "en"),
            "transcript_text": data.get("transcript"),
            "is_auto_generated": data.get("is_generated", True),
            "word_count": data.get("word_count", 0),
            "source": "youtube_api",
        }

    @staticmethod
    def _build_update_set(stmt: insert) -> dict[str, object]:
        """Build SET clause for upsert conflict resolution.

        Args:
            stmt: PostgreSQL INSERT statement with excluded pseudo-table.

        Returns:
            Dictionary mapping column names to excluded values.
        """
        excluded = stmt.excluded
        return {
            "transcript_text": excluded.transcript_text,
            "is_auto_generated": excluded.is_auto_generated,
            "word_count": excluded.word_count,
            "source": excluded.source,
        }
