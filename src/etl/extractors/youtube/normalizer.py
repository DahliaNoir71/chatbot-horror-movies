"""YouTube data normalizer.

Transforms raw YouTube API data into normalized
format for database insertion.
"""

import re
from datetime import datetime
from typing import TypedDict

from src.etl.utils.logger import setup_logger

logger = setup_logger("etl.yt.normalizer")


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================


class ThumbnailInfo(TypedDict, total=False):
    """YouTube thumbnail information."""

    url: str
    width: int
    height: int


class VideoSnippet(TypedDict, total=False):
    """YouTube video snippet data."""

    title: str
    description: str
    channelId: str
    channelTitle: str
    publishedAt: str
    thumbnails: dict[str, ThumbnailInfo]
    tags: list[str]


class VideoStatistics(TypedDict, total=False):
    """YouTube video statistics."""

    viewCount: str
    likeCount: str
    commentCount: str


class VideoContentDetails(TypedDict, total=False):
    """YouTube video content details."""

    duration: str
    videoId: str


class VideoData(TypedDict, total=False):
    """YouTube video API response."""

    id: str
    snippet: VideoSnippet
    statistics: VideoStatistics
    contentDetails: VideoContentDetails


class PlaylistItemData(TypedDict, total=False):
    """YouTube playlist item API response."""

    contentDetails: VideoContentDetails


class TranscriptData(TypedDict, total=False):
    """Transcript extraction result."""

    text: str
    language: str
    is_generated: bool


class NormalizedVideo(TypedDict, total=False):
    """Normalized video for database."""

    id: str
    title: str
    description: str
    channel_id: str
    channel_title: str
    published_at: str | None
    duration: str
    duration_seconds: int
    view_count: int
    like_count: int
    comment_count: int
    thumbnail_url: str
    tags: list[str]
    source_type: str
    source_id: str | None


class NormalizedTranscript(TypedDict):
    """Normalized transcript for database."""

    video_id: str
    text: str
    language: str
    is_generated: bool
    word_count: int


# =============================================================================
# NORMALIZER
# =============================================================================


class YouTubeNormalizer:
    """Normalizes YouTube API data.

    Transforms raw API responses into database-ready
    normalized format.
    """

    # -------------------------------------------------------------------------
    # Video Normalization
    # -------------------------------------------------------------------------

    def normalize_video(
        self,
        video_data: VideoData,
        source_type: str = "playlist",
        source_id: str | None = None,
    ) -> NormalizedVideo | None:
        """Normalize video data from API.

        Args:
            video_data: Raw video data from API.
            source_type: Source type (channel, playlist, search).
            source_id: Source identifier.

        Returns:
            Normalized video dict or None if invalid.
        """
        video_id = video_data.get("id")
        if not video_id:
            return None

        snippet = video_data.get("snippet", {})
        stats = video_data.get("statistics", {})
        content = video_data.get("contentDetails", {})

        return NormalizedVideo(
            id=video_id,
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            channel_id=snippet.get("channelId", ""),
            channel_title=snippet.get("channelTitle", ""),
            published_at=self._parse_datetime(snippet.get("publishedAt")),
            duration=self._parse_duration(content.get("duration", "")),
            duration_seconds=self._duration_to_seconds(content.get("duration", "")),
            view_count=self._safe_int(stats.get("viewCount")),
            like_count=self._safe_int(stats.get("likeCount")),
            comment_count=self._safe_int(stats.get("commentCount")),
            thumbnail_url=self._get_best_thumbnail(snippet.get("thumbnails", {})),
            tags=snippet.get("tags", []),
            source_type=source_type,
            source_id=source_id,
        )

    def normalize_videos(
        self,
        videos_data: list[VideoData],
        source_type: str = "playlist",
        source_id: str | None = None,
    ) -> list[NormalizedVideo]:
        """Normalize multiple videos.

        Args:
            videos_data: List of raw video data.
            source_type: Source type for all videos.
            source_id: Source identifier for all videos.

        Returns:
            List of normalized video dicts (invalid ones filtered).
        """
        normalized: list[NormalizedVideo] = []

        for video in videos_data:
            norm = self.normalize_video(video, source_type, source_id)
            if norm:
                normalized.append(norm)

        return normalized

    # -------------------------------------------------------------------------
    # Transcript Normalization
    # -------------------------------------------------------------------------

    def normalize_transcript(
        self,
        video_id: str,
        transcript_data: TranscriptData | None,
    ) -> NormalizedTranscript | None:
        """Normalize transcript data.

        Args:
            video_id: Associated video ID.
            transcript_data: Raw transcript data or None.

        Returns:
            Normalized transcript dict or None.
        """
        if not transcript_data:
            return None

        return NormalizedTranscript(
            video_id=video_id,
            text=transcript_data.get("text", ""),
            language=transcript_data.get("language", ""),
            is_generated=transcript_data.get("is_generated", False),
            word_count=self._count_words(transcript_data.get("text", "")),
        )

    # -------------------------------------------------------------------------
    # Playlist Item Normalization
    # -------------------------------------------------------------------------

    @staticmethod
    def extract_video_id_from_playlist_item(
        item: PlaylistItemData,
    ) -> str | None:
        """Extract video ID from playlist item.

        Args:
            item: Playlist item data from API.

        Returns:
            Video ID or None.
        """
        content = item.get("contentDetails", {})
        return content.get("videoId")

    def extract_video_ids_from_playlist(
        self,
        items: list[PlaylistItemData],
    ) -> list[str]:
        """Extract all video IDs from playlist items.

        Args:
            items: List of playlist item data.

        Returns:
            List of video IDs (None values filtered).
        """
        ids: list[str] = []

        for item in items:
            video_id = self.extract_video_id_from_playlist_item(item)
            if video_id:
                ids.append(video_id)

        return ids

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_datetime(iso_string: str | None) -> str | None:
        """Parse ISO datetime string.

        Args:
            iso_string: ISO 8601 datetime string.

        Returns:
            Normalized datetime string or None.
        """
        if not iso_string:
            return None

        try:
            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            return dt.isoformat()
        except (ValueError, AttributeError):
            return iso_string

    @staticmethod
    def _parse_duration(iso_duration: str) -> str:
        """Parse ISO 8601 duration to human-readable format.

        Args:
            iso_duration: ISO 8601 duration (e.g., "PT1H30M45S").

        Returns:
            Human-readable duration (e.g., "1:30:45").
        """
        if not iso_duration:
            return "0:00"

        match = re.match(
            r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
            iso_duration,
        )

        if not match:
            return "0:00"

        hours, minutes, seconds = (
            int(match.group(1) or 0),
            int(match.group(2) or 0),
            int(match.group(3) or 0),
        )

        # Single return with conditional expression
        return f"{hours}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes}:{seconds:02d}"

    @staticmethod
    def _duration_to_seconds(iso_duration: str) -> int:
        """Convert ISO 8601 duration to seconds.

        Args:
            iso_duration: ISO 8601 duration (e.g., "PT1H30M45S").

        Returns:
            Duration in seconds.
        """
        if not iso_duration:
            return 0

        match = re.match(
            r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
            iso_duration,
        )

        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def _get_best_thumbnail(thumbnails: dict[str, ThumbnailInfo]) -> str:
        """Get highest quality thumbnail URL.

        Args:
            thumbnails: Thumbnails dict from API.

        Returns:
            Best available thumbnail URL or empty string.
        """
        for quality in ["maxres", "high", "medium", "default"]:
            if quality in thumbnails:
                return thumbnails[quality].get("url", "")
        return ""

    @staticmethod
    def _safe_int(value: str | None) -> int:
        """Safely convert value to int.

        Args:
            value: Value to convert.

        Returns:
            Integer value or 0 if conversion fails.
        """
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _count_words(text: str) -> int:
        """Count words in text.

        Args:
            text: Text to count words in.

        Returns:
            Word count.
        """
        if not text:
            return 0
        return len(text.split())
