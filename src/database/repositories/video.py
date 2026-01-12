"""YouTube video repositories.

Provides CRUD and query operations for videos
and transcripts from YouTube Data API.
"""

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.youtube import FilmVideo, Video, VideoTranscript
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
        stmt = (
            select(Video)
            .outerjoin(Video.transcript)
            .where(VideoTranscript.id == None)  # noqa: E711
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
        """Count videos by channel."""
        stmt = select(Video.channel_title, func.count(Video.id)).group_by(Video.channel_title)
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result if row[0]}


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

    def get_without_embedding(self, limit: int = 100) -> list[VideoTranscript]:
        """Get transcripts missing embeddings.

        Args:
            limit: Maximum results.

        Returns:
            List of transcripts without embeddings.
        """
        stmt = (
            select(VideoTranscript)
            .where(VideoTranscript.embedding == None)  # noqa: E711
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def update_embedding(
        self,
        transcript_id: int,
        embedding: list[float],
    ) -> None:
        """Update transcript embedding vector.

        Args:
            transcript_id: Transcript primary key.
            embedding: Vector embedding (1536 dimensions).
        """
        stmt = (
            update(VideoTranscript)
            .where(VideoTranscript.id == transcript_id)
            .values(embedding=embedding)
        )
        self._session.execute(stmt)
        self._session.flush()

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
                index_elements=["video_id"],
                set_={k: v for k, v in data.items() if k != "video_id"},
            )
            .returning(VideoTranscript)
        )
        result = self._session.execute(stmt)
        self._session.flush()
        return result.scalar_one()


class FilmVideoRepository(BaseRepository[FilmVideo]):
    """Repository for Film-Video association operations.

    Manages the many-to-many relationship between films
    and YouTube videos with match scoring.
    """

    model = FilmVideo

    def __init__(self, session: Session) -> None:
        """Initialize film-video repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_film(self, film_id: int) -> list[FilmVideo]:
        """Get all video associations for a film.

        Args:
            film_id: Film primary key.

        Returns:
            List of associations ordered by match score.
        """
        stmt = (
            select(FilmVideo)
            .where(FilmVideo.film_id == film_id)
            .order_by(FilmVideo.match_score.desc())
        )
        return list(self._session.scalars(stmt).all())

    def get_by_video(self, video_id: int) -> list[FilmVideo]:
        """Get all film associations for a video.

        Args:
            video_id: Video primary key.

        Returns:
            List of associations ordered by match score.
        """
        stmt = (
            select(FilmVideo)
            .where(FilmVideo.video_id == video_id)
            .order_by(FilmVideo.match_score.desc())
        )
        return list(self._session.scalars(stmt).all())

    def link(
        self,
        film_id: int,
        video_id: int,
        match_score: float,
        match_method: str,
    ) -> FilmVideo:
        """Create association between film and video.

        Args:
            film_id: Film primary key.
            video_id: Video primary key.
            match_score: Confidence score (0-1).
            match_method: Method used for matching.

        Returns:
            Created FilmVideo association.
        """
        association = FilmVideo(
            film_id=film_id,
            video_id=video_id,
            match_score=match_score,
            match_method=match_method,
        )
        return self.create(association)
