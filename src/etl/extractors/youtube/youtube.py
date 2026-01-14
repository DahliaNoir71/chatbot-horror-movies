"""YouTube extractor orchestrator.

Orchestrates extraction from YouTube channels and
playlists, including video metadata and transcripts.
"""

from dataclasses import dataclass, field
from typing import Any

from src.etl.extractors.base import BaseExtractor
from src.etl.utils.logger import setup_logger
from src.settings import settings

from .client import YouTubeClient, YouTubeQuotaError
from .normalizer import YouTubeNormalizer
from .transcript import TranscriptExtractor

logger = setup_logger("etl.yt.yt")


# =============================================================================
# STATISTICS
# =============================================================================


@dataclass
class YouTubeStats:
    """Extraction statistics tracker."""

    channels_processed: int = 0
    playlists_processed: int = 0
    videos_extracted: int = 0
    transcripts_extracted: int = 0
    api_calls: int = 0
    quota_used: int = 0
    errors: int = 0
    seen_video_ids: set[str] = field(default_factory=set)

    def add_video(self, video_id: str) -> bool:
        """Track video and return True if new.

        Args:
            video_id: YouTube video ID.

        Returns:
            True if video is new, False if duplicate.
        """
        if video_id in self.seen_video_ids:
            return False
        self.seen_video_ids.add(video_id)
        self.videos_extracted += 1
        return True


# =============================================================================
# EXTRACTOR
# =============================================================================


class YouTubeExtractor(BaseExtractor):
    """Extracts video data from YouTube channels and playlists.

    Supports extraction from:
    - Channel handles (fetches uploads playlist)
    - Playlist IDs (direct extraction)

    Includes optional transcript extraction.

    Attributes:
        stats: Extraction statistics.
    """

    name = "youtube"

    def __init__(self) -> None:
        """Initialize YouTube extractor."""
        super().__init__()
        self._normalizer = YouTubeNormalizer()
        self._transcript_extractor = TranscriptExtractor()
        self._cfg = settings.youtube
        self._stats = YouTubeStats()

    # -------------------------------------------------------------------------
    # Configuration Validation
    # -------------------------------------------------------------------------

    def validate_config(self) -> None:
        """Validate YouTube API key is configured.

        Raises:
            ValueError: If API key is missing.
        """
        if not self._cfg.is_configured:
            raise ValueError("YOUTUBE_API_KEY not configured in .env")

    # -------------------------------------------------------------------------
    # Main Extraction
    # -------------------------------------------------------------------------

    def extract(
        self,
        include_transcripts: bool = True,
        max_videos: int | None = None,
        channel_filter: list[str] | None = None,
        playlist_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute YouTube extraction.

        Reads channel handles and playlist IDs from settings.

        Args:
            include_transcripts: Whether to extract transcripts.
            max_videos: Override max videos limit.
            channel_filter: Only extract from these channels.
            playlist_filter: Only extract from these playlists.

        Returns:
            List of normalized video dictionaries.
        """
        self._start_extraction()
        self._stats = YouTubeStats()

        try:
            self.validate_config()
            max_vids = max_videos or self._cfg.max_videos

            all_videos: list[dict[str, Any]] = []

            with YouTubeClient() as client:
                # Extract from channels
                all_videos = self._extract_channels(
                    client=client,
                    channel_filter=channel_filter,
                    max_videos=max_vids,
                    all_videos=all_videos,
                )

                # Extract from playlists
                all_videos = self._extract_playlists(
                    client=client,
                    playlist_filter=playlist_filter,
                    max_videos=max_vids,
                    all_videos=all_videos,
                )

                # Update stats from client
                self._stats.api_calls = client.api_calls
                self._stats.quota_used = client.quota_used

            # Extract transcripts if requested
            if include_transcripts:
                self._enrich_with_transcripts(all_videos)

            self._log_stats()
            return all_videos

        except YouTubeQuotaError as e:
            logger.error(f"Quota exceeded: {e}")
            self._stats.errors += 1
            raise

        finally:
            self._end_extraction()

    # -------------------------------------------------------------------------
    # Channel Extraction
    # -------------------------------------------------------------------------

    def _extract_channels(
        self,
        client: YouTubeClient,
        channel_filter: list[str] | None,
        max_videos: int,
        all_videos: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract videos from configured channels.

        Args:
            client: YouTube API client.
            channel_filter: Optional channel handles filter.
            max_videos: Max videos per channel.
            all_videos: Current video list to extend.

        Returns:
            Updated video list.
        """
        channels = self._cfg.channel_handles

        if channel_filter:
            channels = [c for c in channels if c in channel_filter]

        for handle in channels:
            videos = self._extract_single_channel(client, handle, max_videos)
            all_videos.extend(videos)
            self._stats.channels_processed += 1

        return all_videos

    def _extract_single_channel(
        self,
        client: YouTubeClient,
        handle: str,
        max_videos: int,
    ) -> list[dict[str, Any]]:
        """Extract videos from a single channel.

        Args:
            client: YouTube API client.
            handle: Channel handle (e.g., "@Monstresdefilms").
            max_videos: Maximum videos to extract.

        Returns:
            List of normalized video dictionaries.
        """
        logger.info(f"Extracting channel: {handle}")

        # Resolve handle to channel info
        channel_info = client.resolve_channel_handle(handle)
        if not channel_info:
            logger.warning(f"Channel not found: {handle}")
            self._stats.errors += 1
            return []

        logger.info(f"Channel resolved: {handle} -> {channel_info['id']} ({channel_info['title']})")

        # Get videos from uploads playlist
        uploads_playlist = channel_info["uploads_playlist_id"]
        return self._extract_playlist_videos(
            client=client,
            playlist_id=uploads_playlist,
            source_type="channel",
            source_id=handle,
            max_videos=max_videos,
        )

    # -------------------------------------------------------------------------
    # Playlist Extraction
    # -------------------------------------------------------------------------

    def _extract_playlists(
        self,
        client: YouTubeClient,
        playlist_filter: list[str] | None,
        max_videos: int,
        all_videos: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract videos from configured playlists.

        Args:
            client: YouTube API client.
            playlist_filter: Optional playlist IDs filter.
            max_videos: Max videos per playlist.
            all_videos: Current video list to extend.

        Returns:
            Updated video list.
        """
        playlists = self._cfg.playlist_ids

        if playlist_filter:
            playlists = [p for p in playlists if p in playlist_filter]

        for playlist_id in playlists:
            videos = self._extract_playlist_videos(
                client=client,
                playlist_id=playlist_id,
                source_type="playlist",
                source_id=playlist_id,
                max_videos=max_videos,
            )
            all_videos.extend(videos)
            self._stats.playlists_processed += 1

        return all_videos

    def _extract_playlist_videos(
        self,
        client: YouTubeClient,
        playlist_id: str,
        source_type: str,
        source_id: str,
        max_videos: int,
    ) -> list[dict[str, Any]]:
        """Extract videos from a playlist.

        Args:
            client: YouTube API client.
            playlist_id: YouTube playlist ID.
            source_type: "channel" or "playlist".
            source_id: Channel handle or playlist ID.
            max_videos: Maximum videos to extract.

        Returns:
            List of normalized video dictionaries.
        """
        logger.info(f"Extracting playlist: {playlist_id}")

        # Get playlist items
        playlist_items = client.get_playlist_videos(playlist_id, max_videos)
        if not playlist_items:
            return []

        # Extract video IDs (deduplicated)
        video_ids = self._extract_unique_video_ids(playlist_items)
        if not video_ids:
            return []

        # Get video details
        video_details = client.get_videos_details(video_ids)

        # Normalize videos
        normalized = self._normalizer.normalize_videos(
            video_details,
            source_type=source_type,
            source_id=source_id,
        )

        logger.info(f"Playlist extracted: {playlist_id} - {len(normalized)} videos")
        return normalized

    def _extract_unique_video_ids(
        self,
        playlist_items: list[dict[str, Any]],
    ) -> list[str]:
        """Extract unique video IDs from playlist items.

        Args:
            playlist_items: Raw playlist item data.

        Returns:
            List of unique video IDs.
        """
        ids: list[str] = []

        for item in playlist_items:
            video_id = self._normalizer.extract_video_id_from_playlist_item(item)
            if video_id and self._stats.add_video(video_id):
                ids.append(video_id)

        return ids

    # -------------------------------------------------------------------------
    # Transcript Enrichment
    # -------------------------------------------------------------------------

    def _enrich_with_transcripts(
        self,
        videos: list[dict[str, Any]],
    ) -> None:
        """Enrich videos with transcript data.

        Args:
            videos: List of video dicts to enrich in-place.
        """
        logger.info(f"Extracting transcripts for {len(videos)} videos...")

        for video in videos:
            video_id = video.get("id")
            if not video_id:
                continue

            transcript = self._transcript_extractor.extract(video_id)
            if transcript:
                video["transcript"] = transcript.get("text", "")
                video["transcript_language"] = transcript.get("language", "")
                video["transcript_is_generated"] = transcript.get("is_generated", False)
                self._stats.transcripts_extracted += 1

    # -------------------------------------------------------------------------
    # Single Video Extraction
    # -------------------------------------------------------------------------

    def extract_video(
        self,
        video_id: str,
        include_transcript: bool = True,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Extract single video with optional transcript.

        Args:
            video_id: YouTube video ID.
            include_transcript: Whether to extract transcript.

        Returns:
            Tuple of (video_data, transcript_data).
        """
        with YouTubeClient() as client:
            video = client.get_video_details(video_id)

            if not video:
                return None, None

            normalized = self._normalizer.normalize_video(video, "direct", video_id)

            transcript = None
            if include_transcript and normalized:
                raw = self._transcript_extractor.extract(video_id)
                transcript = self._normalizer.normalize_transcript(video_id, raw)

            return normalized, transcript

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    def _log_stats(self) -> None:
        """Log extraction statistics."""
        logger.info("=" * 60)
        logger.info("📊 YOUTUBE EXTRACTION STATS")
        logger.info("-" * 60)
        logger.info(f"Channels processed  : {self._stats.channels_processed}")
        logger.info(f"Playlists processed : {self._stats.playlists_processed}")
        logger.info(f"Videos extracted    : {self._stats.videos_extracted}")
        logger.info(f"Transcripts         : {self._stats.transcripts_extracted}")
        logger.info(f"API calls           : {self._stats.api_calls}")
        logger.info(f"Quota used          : {self._stats.quota_used}")
        logger.info(f"Errors              : {self._stats.errors}")
        logger.info(f"Duration            : {self.metrics.duration_seconds:.2f}s")
        logger.info("=" * 60)

    @property
    def stats(self) -> YouTubeStats:
        """Get current extraction statistics."""
        return self._stats
