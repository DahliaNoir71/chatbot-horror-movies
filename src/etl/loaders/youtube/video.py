"""YouTube video data loader.

Handles video entity insertion with upsert on youtube_id.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.database.models.youtube.video import Video
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types import NormalizedVideoData


class VideoLoader(BaseLoader):
    """Loader for YouTube video data.

    Uses youtube_id as unique constraint for upsert operations.
    """

    name = "youtube.video"

    def load(self, data: list[NormalizedVideoData]) -> LoaderStats:
        """Load videos into database.

        Args:
            data: List of normalized video data dictionaries.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        if not data:
            return self.stats

        total = len(data)
        self._logger.info(f"Loading {total} videos")

        for idx, video_data in enumerate(data, 1):
            self._upsert_video(video_data)
            self._log_progress(idx, total)

        self._session.flush()
        self._log_summary()
        return self.stats

    def _upsert_video(self, data: NormalizedVideoData) -> None:
        """Upsert a single video record.

        Args:
            data: Normalized video data dictionary.
        """
        try:
            stmt = insert(Video).values(**self._build_values(data))
            stmt = stmt.on_conflict_do_update(
                index_elements=["youtube_id"],
                set_=self._build_update_set(stmt),
            )
            self._session.execute(stmt)
            self._record_insert()
        except Exception as e:
            self._record_error(f"Video {data['youtube_id']} failed: {e}")

    def get_id_by_youtube_id(self, youtube_id: str) -> int | None:
        """Get internal video ID by YouTube ID.

        Args:
            youtube_id: YouTube video identifier.

        Returns:
            Internal database ID or None if not found.
        """
        stmt = select(Video.id).where(Video.youtube_id == youtube_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_id_map(self, youtube_ids: list[str]) -> dict[str, int]:
        """Get mapping of youtube_id to internal id for given IDs.

        Args:
            youtube_ids: List of YouTube video identifiers.

        Returns:
            Dictionary mapping YouTube IDs to internal IDs.
        """
        if not youtube_ids:
            return {}

        stmt = select(Video.youtube_id, Video.id).where(Video.youtube_id.in_(youtube_ids))
        rows = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in rows}

    @staticmethod
    def _build_values(data: NormalizedVideoData) -> dict[str, object]:
        """Build INSERT values from normalized data.

        Args:
            data: Normalized video data dictionary.

        Returns:
            Dictionary of column-value pairs for INSERT.
        """
        return {
            "youtube_id": data["youtube_id"],
            "title": data["title"],
            "description": data.get("description"),
            "channel_id": data.get("channel_id"),
            "channel_title": data.get("channel_title"),
            "view_count": data.get("view_count", 0),
            "like_count": data.get("like_count", 0),
            "comment_count": data.get("comment_count", 0),
            "duration": data.get("duration"),
            "published_at": data.get("published_at"),
            "thumbnail_url": data.get("thumbnail_url"),
            "video_type": data.get("video_type"),
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
            "title": excluded.title,
            "description": excluded.description,
            "channel_id": excluded.channel_id,
            "channel_title": excluded.channel_title,
            "view_count": excluded.view_count,
            "like_count": excluded.like_count,
            "comment_count": excluded.comment_count,
            "duration": excluded.duration,
            "published_at": excluded.published_at,
            "thumbnail_url": excluded.thumbnail_url,
            "video_type": excluded.video_type,
        }
