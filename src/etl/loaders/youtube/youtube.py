"""YouTube loader orchestrator.

Coordinates loading of YouTube data bundles into the database
with proper ordering and transaction management.
"""

from typing import Any

from sqlalchemy.orm import Session

from src.etl.loaders.base import LoaderStats
from src.etl.loaders.youtube.film_video import FilmVideoLoader
from src.etl.loaders.youtube.transcript import TranscriptLoader
from src.etl.loaders.youtube.video import VideoLoader
from src.etl.types import FilmMatchResult, NormalizedTranscriptData, NormalizedVideoData
from src.etl.utils.logger import setup_logger


class YouTubeLoader:
    """Orchestrates loading of YouTube extraction data.

    Handles the full pipeline from YouTubeExtractor output
    to database insertion with proper FK ordering:
    1. Videos (must exist before transcripts/associations)
    2. Transcripts (requires video_id)
    3. Film-video associations (requires video_id)
    """

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session
        self._logger = setup_logger("etl.loader.youtube")

        # Initialize sub-loaders
        self._video = VideoLoader(session)
        self._transcript = TranscriptLoader(session)
        self._film_video = FilmVideoLoader(session)

    @property
    def video(self) -> VideoLoader:
        """Get video loader.

        Returns:
            VideoLoader instance.
        """
        return self._video

    @property
    def transcript(self) -> TranscriptLoader:
        """Get transcript loader.

        Returns:
            TranscriptLoader instance.
        """
        return self._transcript

    @property
    def film_video(self) -> FilmVideoLoader:
        """Get film-video association loader.

        Returns:
            FilmVideoLoader instance.
        """
        return self._film_video

    def load_videos(self, videos: list[NormalizedVideoData]) -> LoaderStats:
        """Load videos into database.

        Args:
            videos: List of normalized video data.

        Returns:
            LoaderStats with operation results.
        """
        stats = self._video.load(videos)
        self._session.flush()
        return stats

    def load_transcripts(
        self,
        transcripts: list[NormalizedTranscriptData],
    ) -> LoaderStats:
        """Load transcripts into database.

        Args:
            transcripts: List of normalized transcript data.

        Returns:
            LoaderStats with operation results.
        """
        stats = self._transcript.load(transcripts)
        self._session.flush()
        return stats

    def load_associations(
        self,
        associations: list[FilmMatchResult],
    ) -> LoaderStats:
        """Load film-video associations into database.

        Args:
            associations: List of film match results.

        Returns:
            LoaderStats with operation results.
        """
        stats = self._film_video.load(associations)
        self._session.flush()
        return stats

    def load_bundle(self, bundle: dict[str, Any]) -> bool:
        """Load a single YouTube bundle into database.

        Args:
            bundle: Dict with:
                - video: NormalizedVideoData
                - transcript: NormalizedTranscriptData (optional)
                - film_id: int (optional, for association)
                - match_score: float (optional)
                - match_method: str (optional)

        Returns:
            True if successful, False otherwise.
        """
        try:
            video_id = self._load_video(bundle)
            if video_id is None:
                return False

            self._load_transcript(bundle, video_id)
            self._load_association(bundle, video_id)
            return True

        except Exception as e:
            self._logger.error(f"Bundle load failed: {e}")
            return False

    def load_bundles(self, bundles: list[dict[str, Any]]) -> LoaderStats:
        """Load multiple YouTube bundles.

        Args:
            bundles: List of YouTube bundles.

        Returns:
            Combined LoaderStats.
        """
        stats = LoaderStats()
        total = len(bundles)

        self._logger.info(f"Loading {total} YouTube bundles")

        for idx, bundle in enumerate(bundles, 1):
            if self.load_bundle(bundle):
                stats.inserted += 1
            else:
                stats.errors += 1

            self._flush_periodically(idx, total)

        self._session.flush()
        self._log_completion(stats)
        return stats

    def _load_video(self, bundle: dict[str, Any]) -> int | None:
        """Load video and return internal ID.

        Args:
            bundle: YouTube bundle dictionary.

        Returns:
            Internal video ID or None if load failed.
        """
        video_data = bundle.get("video")
        if not video_data:
            return None

        self._video.load([video_data])
        self._session.flush()
        return self._video.get_id_by_youtube_id(video_data["youtube_id"])

    def _load_transcript(self, bundle: dict[str, Any], video_id: int) -> None:
        """Load transcript for video if present.

        Args:
            bundle: YouTube bundle dictionary.
            video_id: Internal database video ID.
        """
        transcript_data = bundle.get("transcript")
        if not transcript_data:
            return

        transcript_data["video_id"] = video_id
        self._transcript.load([transcript_data])

    def _load_association(self, bundle: dict[str, Any], video_id: int) -> None:
        """Load film-video association if film_id present.

        Args:
            bundle: YouTube bundle dictionary.
            video_id: Internal database video ID.
        """
        film_id = bundle.get("film_id")
        if not film_id:
            return

        self._film_video.load_single(
            film_id=film_id,
            video_id=video_id,
            match_score=bundle.get("match_score", 1.0),
            match_method=bundle.get("match_method", "title_similarity"),
        )

    def _flush_periodically(self, current: int, total: int) -> None:
        """Flush session every 50 items.

        Args:
            current: Current item index.
            total: Total items to process.
        """
        if current % 50 == 0:
            self._logger.info(f"Progress: {current}/{total}")
            self._session.flush()

    def _log_completion(self, stats: LoaderStats) -> None:
        """Log completion message.

        Args:
            stats: Final loader statistics.
        """
        self._logger.info(f"Complete: {stats.inserted} OK, {stats.errors} errors")
