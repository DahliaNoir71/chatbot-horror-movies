"""YouTube data normalizer.

Transforms raw YouTube API responses into normalized
data structures ready for database insertion.
"""

import re
from datetime import datetime
from typing import Any, ClassVar

from src.etl.types import NormalizedTranscriptData, NormalizedVideoData, YouTubeVideoData
from src.etl.utils.logger import setup_logger


class YouTubeNormalizer:
    """Normalizes YouTube API data for database insertion.

    Transforms raw API responses into typed dictionaries
    matching the database schema.
    """

    _TYPE_KEYWORDS: ClassVar[dict[str, list[str]]] = {
        "review": ["review", "critique", "avis", "analysis"],
        "trailer": ["trailer", "bande-annonce", "teaser"],
        "interview": ["interview", "entretien", "q&a"],
        "recap": ["recap", "résumé", "explained", "ending explained"],
        "ranking": ["ranking", "top 10", "top 5", "best of", "worst"],
        "reaction": ["reaction", "réaction", "first time watching"],
    }

    def __init__(self) -> None:
        """Initialize normalizer with logger."""
        self._logger = setup_logger("etl.youtube.normalizer")

    # -------------------------------------------------------------------------
    # Video Normalization
    # -------------------------------------------------------------------------

    def normalize_video(self, raw_data: dict[str, Any]) -> NormalizedVideoData:
        """Normalize video data from API response.

        Args:
            raw_data: Raw video item from YouTube API.

        Returns:
            Normalized video data ready for database insertion.
        """
        snippet = raw_data.get("snippet", {})
        statistics = raw_data.get("statistics", {})
        content_details = raw_data.get("contentDetails", {})

        return NormalizedVideoData(
            youtube_id=self._extract_video_id(raw_data),
            title=self._clean_text(snippet.get("title", "")),
            description=self._truncate_description(snippet.get("description")),
            channel_id=snippet.get("channelId"),
            channel_title=snippet.get("channelTitle"),
            view_count=self._parse_int(statistics.get("viewCount"), 0),
            like_count=self._parse_int(statistics.get("likeCount"), 0),
            comment_count=self._parse_int(statistics.get("commentCount"), 0),
            duration=content_details.get("duration"),
            published_at=self._parse_datetime(snippet.get("publishedAt")),
            thumbnail_url=self._extract_thumbnail(snippet.get("thumbnails")),
            video_type=self._detect_video_type(snippet),
        )

    def normalize_video_from_playlist_item(
        self,
        item: dict[str, Any],
    ) -> YouTubeVideoData:
        """Normalize video data from playlist item.

        Playlist items have different structure than video details.

        Args:
            item: Playlist item from API.

        Returns:
            Partial video data (requires details enrichment).
        """
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})

        return YouTubeVideoData(
            youtube_id=content_details.get("videoId", ""),
            title=self._clean_text(snippet.get("title", "")),
            description=snippet.get("description"),
            channel_id=snippet.get("channelId"),
            channel_title=snippet.get("channelTitle"),
            published_at=snippet.get("publishedAt"),
            thumbnail_url=self._extract_thumbnail(snippet.get("thumbnails")),
        )

    def _extract_video_id(self, raw_data: dict[str, Any]) -> str:
        """Extract video ID from various response formats.

        Args:
            raw_data: Raw API response item.

        Returns:
            YouTube video ID or empty string if not found.
        """
        # Try direct ID or search result format first
        video_id = self._try_extract_direct_id(raw_data)
        if video_id:
            return video_id

        # Fallback to content details format (playlist items)
        return raw_data.get("contentDetails", {}).get("videoId", "")

    @staticmethod
    def _try_extract_direct_id(raw_data: dict[str, Any]) -> str | None:
        """Try to extract ID from direct or search result format.

        Args:
            raw_data: Raw API response item.

        Returns:
            Video ID if found, None otherwise.
        """
        raw_id = raw_data.get("id")
        if isinstance(raw_id, str):
            return raw_id
        if isinstance(raw_id, dict):
            return raw_id.get("videoId")
        return None

    # -------------------------------------------------------------------------
    # Transcript Normalization
    # -------------------------------------------------------------------------

    def normalize_transcript(
        self,
        video_db_id: int,
        transcript_text: str,
        language: str = "en",
        is_generated: bool = False,
    ) -> NormalizedTranscriptData:
        """Normalize transcript data.

        Args:
            video_db_id: Database ID of the video.
            transcript_text: Full transcript text.
            language: Transcript language code.
            is_generated: Whether auto-generated.

        Returns:
            Normalized transcript data ready for database insertion.
        """
        cleaned_text = self._clean_transcript(transcript_text)

        return NormalizedTranscriptData(
            video_id=video_db_id,
            transcript=cleaned_text,
            language=language,
            is_generated=is_generated,
            word_count=self._count_words(cleaned_text),
        )

    def _clean_transcript(self, text: str) -> str:
        """Clean transcript text by normalizing whitespace and punctuation.

        Args:
            text: Raw transcript text.

        Returns:
            Cleaned text with normalized spacing and punctuation.
        """
        if not text:
            return ""

        cleaned = self._normalize_whitespace(text)
        cleaned = self._remove_repeated_punctuation(cleaned)
        return cleaned.strip()

    # -------------------------------------------------------------------------
    # Text Helpers (Static Methods)
    # -------------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str | None) -> str:
        """Clean and normalize text.

        Args:
            text: Raw text string.

        Returns:
            Cleaned text with normalized whitespace.
        """
        if not text:
            return ""

        cleaned = text.strip()
        return re.sub(r"\s+", " ", cleaned)

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalize whitespace in text.

        Args:
            text: Text with irregular whitespace.

        Returns:
            Text with single spaces between words.
        """
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _remove_repeated_punctuation(text: str) -> str:
        """Remove repeated punctuation marks.

        Args:
            text: Text with possible repeated punctuation.

        Returns:
            Cleaned text with single punctuation marks.
        """
        return re.sub(r"([.!?])\1+", r"\1", text)

    @staticmethod
    def _truncate_description(
        description: str | None,
        max_length: int = 5000,
    ) -> str | None:
        """Truncate description to max length.

        Args:
            description: Raw description text.
            max_length: Maximum character length.

        Returns:
            Truncated description or None if input is empty.
        """
        if not description:
            return None

        cleaned = YouTubeNormalizer._clean_text(description)
        if len(cleaned) <= max_length:
            return cleaned

        return cleaned[: max_length - 3] + "..."

    @staticmethod
    def _count_words(text: str) -> int:
        """Count words in text.

        Args:
            text: Text to count words in.

        Returns:
            Number of words in text.
        """
        if not text:
            return 0
        return len(text.split())

    # -------------------------------------------------------------------------
    # Parsing Helpers (Static Methods)
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_int(value: str | int | None, default: int = 0) -> int:
        """Parse integer from string or return default.

        Args:
            value: Value to parse (string, int, or None).
            default: Default value if parsing fails.

        Returns:
            Parsed integer or default value.
        """
        if value is None:
            return default

        if isinstance(value, int):
            return value

        return YouTubeNormalizer._safe_int_cast(value, default)

    @staticmethod
    def _safe_int_cast(value: str, default: int) -> int:
        """Safely cast string to int.

        Args:
            value: String value to cast.
            default: Default if casting fails.

        Returns:
            Parsed integer or default.
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse ISO datetime string.

        Args:
            value: ISO format datetime string.

        Returns:
            Parsed datetime or None if parsing fails.
        """
        if not value:
            return None

        try:
            # Handle YouTube's ISO format with Z suffix
            cleaned = value.replace("Z", "+00:00")
            return datetime.fromisoformat(cleaned)
        except (ValueError, TypeError):
            self._logger.warning(f"Failed to parse datetime: {value}")
            return None

    @staticmethod
    def _extract_thumbnail(thumbnails: dict[str, Any] | None) -> str | None:
        """Extract best thumbnail URL.

        Priority order: maxres > high > medium > default.

        Args:
            thumbnails: Thumbnails dict from API response.

        Returns:
            Best available thumbnail URL or None.
        """
        if not thumbnails:
            return None

        for quality in ["maxres", "high", "medium", "default"]:
            if quality in thumbnails:
                return thumbnails[quality].get("url")

        return None

    # -------------------------------------------------------------------------
    # Video Type Detection
    # -------------------------------------------------------------------------

    def _detect_video_type(self, snippet: dict[str, Any]) -> str | None:
        """Detect video type from title and description.

        Args:
            snippet: Video snippet data from API.

        Returns:
            Detected video type or None if unclassified.
        """
        title = snippet.get("title", "").lower()
        description = snippet.get("description", "").lower()
        combined = f"{title} {description}"

        return self._classify_video_content(combined)

    @staticmethod
    def _classify_video_content(text: str) -> str | None:
        """Classify video based on text content.

        Matches text against predefined keyword patterns
        to determine video category.

        Args:
            text: Combined title and description in lowercase.

        Returns:
            Video type classification or None if no match.
        """
        for video_type, keywords in YouTubeNormalizer._TYPE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return video_type

        return None

    # -------------------------------------------------------------------------
    # Batch Normalization
    # -------------------------------------------------------------------------

    def normalize_videos_batch(
        self,
        raw_videos: list[dict[str, Any]],
    ) -> list[NormalizedVideoData]:
        """Normalize multiple videos in batch.

        Args:
            raw_videos: List of raw video items from API.

        Returns:
            List of normalized video data, skipping failed items.
        """
        normalized: list[NormalizedVideoData] = []

        for raw in raw_videos:
            self._try_normalize_video(raw, normalized)

        return normalized

    def _try_normalize_video(
        self,
        raw: dict[str, Any],
        results: list[NormalizedVideoData],
    ) -> None:
        """Try to normalize a single video and append to results.

        Args:
            raw: Raw video data from API.
            results: List to append normalized data to.
        """
        try:
            results.append(self.normalize_video(raw))
        except Exception as e:
            video_id = self._extract_video_id(raw)
            self._logger.warning(f"Failed to normalize video {video_id}: {e}")
