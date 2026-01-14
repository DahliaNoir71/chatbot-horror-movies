"""YouTube video repository.

Provides CRUD and query operations for videos
from YouTube Data API.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.youtube import Video, VideoTranscript
from src.database.repositories.base import BaseRepository


class VideoRepository(BaseRepository[Video]):
    """Repository for Video entity operations.

    Videos are YouTube content collected via Data API v3.
    """

    model = Video

    def __init__(self, session: Session) -> None:
        """Initialize video repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_youtube_id(self, youtube_id: str) -> Video | None:
        """Retrieve video by YouTube identifier.

        Args:
            youtube_id: YouTube video ID.

        Returns:
            Video instance or None.
        """
        return self.get_by_field("youtube_id", youtube_id)

    def get_youtube_ids(self) -> set[str]:
        """Get all existing YouTube IDs.

        Returns:
            Set of YouTube IDs in database.
        """
        stmt = select(Video.youtube_id)
        return set(self._session.scalars(stmt).all())

    def get_by_channel(self, channel_id: str, limit: int = 100) -> list[Video]:
        """Get videos from a specific channel.

        Args:
            channel_id: YouTube channel ID.
            limit: Maximum results.

        Returns:
            List of videos from that channel.
        """
        stmt = (
            select(Video)
            .where(Video.channel_id == channel_id)
            .order_by(Video.published_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_without_transcript(self, limit: int = 100) -> list[Video]:
        """Get videos missing transcripts.

        Args:
            limit: Maximum results.

        Returns:
            List of videos without transcripts.
        """
        subquery = select(VideoTranscript.video_id)
        stmt = (
            select(Video)
            .where(Video.id.not_in(subquery))
            .order_by(Video.view_count.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def search_by_title(self, query: str, limit: int = 20) -> list[Video]:
        """Search videos by title.

        Args:
            query: Search query string.
            limit: Maximum results.

        Returns:
            List of matching videos.
        """
        stmt = (
            select(Video)
            .where(Video.title.ilike(f"%{query}%"))
            .order_by(Video.view_count.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def upsert(self, data: dict[str, Any]) -> Video:
        """Insert or update a single video.

        Args:
            data: Video data with youtube_id.

        Returns:
            Upserted video instance.
        """
        stmt = (
            insert(Video)
            .values(**data)
            .on_conflict_do_update(
                index_elements=["youtube_id"],
                set_={k: v for k, v in data.items() if k != "youtube_id"},
            )
            .returning(Video)
        )
        result = self._session.execute(stmt)
        self._session.flush()
        return result.scalar_one()

    def bulk_upsert(self, videos_data: list[dict[str, Any]]) -> int:
        """Bulk insert or update videos.

        Args:
            videos_data: List of video dictionaries.

        Returns:
            Number of videos processed.
        """
        if not videos_data:
            return 0

        stmt = insert(Video).values(videos_data)
        update_cols = {
            col.name: col for col in stmt.excluded if col.name not in ("id", "youtube_id")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["youtube_id"],
            set_=update_cols,
        )
        self._session.execute(stmt)
        self._session.flush()
        return len(videos_data)

    def get_stats(self) -> dict[str, Any]:
        """Get video collection statistics.

        Returns:
            Dictionary with various stats.
        """
        total = self.count()
        total_views = self._session.scalar(select(func.sum(Video.view_count)))
        with_transcript = self._session.scalar(select(func.count(VideoTranscript.id)))
        by_channel = self._count_by_channel()

        return {
            "total": total,
            "total_views": total_views or 0,
            "with_transcript": with_transcript or 0,
            "channels": len(by_channel),
        }

    def _count_by_channel(self) -> dict[str, int]:
        """Count videos by channel.

        Returns:
            Dictionary mapping channel_title to count.
        """
        stmt = select(Video.channel_title, func.count(Video.id)).group_by(Video.channel_title)
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result if row[0]}
