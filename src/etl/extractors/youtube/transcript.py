"""YouTube transcript extractor.

Extracts video transcripts/subtitles using
youtube_transcript_api library.
"""

import logging
from typing import TypedDict

from youtube_transcript_api import (
    NoTranscriptFound,
    Transcript,
    TranscriptList,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

logger = logging.getLogger(__name__)

# Preferred languages for transcripts (priority order)
PREFERRED_LANGUAGES = ["en", "en-US", "en-GB", "fr", "es", "de"]


class TranscriptResult(TypedDict):
    """Structured transcript extraction result."""

    text: str
    language: str
    is_generated: bool
    segments: list[dict[str, str | float]]


class TranscriptExtractor:
    """Extracts transcripts from YouTube videos.

    Uses youtube_transcript_api to fetch available
    transcripts in preferred languages.

    Attributes:
        preferred_languages: Language codes in priority order.
    """

    def __init__(
        self,
        preferred_languages: list[str] | None = None,
    ) -> None:
        """Initialize transcript extractor.

        Args:
            preferred_languages: Language codes in priority order.
        """
        self._preferred_languages = preferred_languages or PREFERRED_LANGUAGES

    # -------------------------------------------------------------------------
    # Main Extraction
    # -------------------------------------------------------------------------

    def extract(self, video_id: str) -> TranscriptResult | None:
        """Extract transcript for a video.

        Args:
            video_id: YouTube video ID.

        Returns:
            Dict with text, language, is_generated or None.
        """
        transcript_list = self._get_transcript_list(video_id)
        if transcript_list is None:
            return None
        return self._get_best_transcript(transcript_list)

    @staticmethod
    def _get_transcript_list(video_id: str) -> TranscriptList | None:
        """Fetch transcript list for video.

        Args:
            video_id: YouTube video ID.

        Returns:
            TranscriptList or None if unavailable.
        """
        try:
            return YouTubeTranscriptApi.list_transcripts(video_id)
        except TranscriptsDisabled:
            logger.debug(f"Transcripts disabled: {video_id}")
        except NoTranscriptFound:
            logger.debug(f"No transcript found: {video_id}")
        except Exception as e:
            logger.warning(f"Transcript error for {video_id}: {e}")
        return None

    def extract_batch(
        self,
        video_ids: list[str],
    ) -> dict[str, TranscriptResult | None]:
        """Extract transcripts for multiple videos.

        Args:
            video_ids: List of video IDs.

        Returns:
            Dict mapping video_id to transcript data or None.
        """
        results: dict[str, TranscriptResult | None] = {}
        for video_id in video_ids:
            results[video_id] = self.extract(video_id)
        return results

    # -------------------------------------------------------------------------
    # Transcript Selection
    # -------------------------------------------------------------------------

    def _get_best_transcript(
        self,
        transcript_list: TranscriptList,
    ) -> TranscriptResult | None:
        """Get best available transcript from list.

        Tries manual transcripts first, then auto-generated.

        Args:
            transcript_list: YouTubeTranscriptApi transcript list.

        Returns:
            Transcript dict or None.
        """
        transcript = self._try_manual_transcript(transcript_list)
        if transcript:
            return transcript
        return self._try_generated_transcript(transcript_list)

    def _try_manual_transcript(
        self,
        transcript_list: TranscriptList,
    ) -> TranscriptResult | None:
        """Try to get manual transcript in preferred language.

        Args:
            transcript_list: YouTubeTranscriptApi transcript list.

        Returns:
            Transcript dict or None.
        """
        try:
            transcript = transcript_list.find_manually_created_transcript(self._preferred_languages)
            return self._format_transcript(transcript, is_generated=False)
        except NoTranscriptFound:
            return None

    def _try_generated_transcript(
        self,
        transcript_list: TranscriptList,
    ) -> TranscriptResult | None:
        """Try to get auto-generated transcript.

        Args:
            transcript_list: YouTubeTranscriptApi transcript list.

        Returns:
            Transcript dict or None.
        """
        try:
            transcript = transcript_list.find_generated_transcript(self._preferred_languages)
            return self._format_transcript(transcript, is_generated=True)
        except NoTranscriptFound:
            return None

    def _format_transcript(
        self,
        transcript: Transcript,
        is_generated: bool,
    ) -> TranscriptResult:
        """Format transcript data to standard structure.

        Args:
            transcript: YouTubeTranscriptApi transcript object.
            is_generated: Whether transcript is auto-generated.

        Returns:
            Formatted transcript dict.
        """
        segments = transcript.fetch()
        full_text = self._segments_to_text(segments)

        return TranscriptResult(
            text=full_text,
            language=transcript.language_code,
            is_generated=is_generated,
            segments=segments,
        )

    @staticmethod
    def _segments_to_text(segments: list[dict[str, str | float]]) -> str:
        """Convert transcript segments to full text.

        Args:
            segments: List of transcript segments.

        Returns:
            Full transcript text.
        """
        texts = [str(seg.get("text", "")) for seg in segments]
        return " ".join(texts).strip()

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def get_available_languages(video_id: str) -> list[str]:
        """Get list of available transcript languages.

        Args:
            video_id: YouTube video ID.

        Returns:
            List of language codes.
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            return [t.language_code for t in transcript_list]
        except (TranscriptsDisabled, NoTranscriptFound):
            return []

    @staticmethod
    def has_transcript(video_id: str) -> bool:
        """Check if video has any transcript available.

        Args:
            video_id: YouTube video ID.

        Returns:
            True if transcript available.
        """
        try:
            YouTubeTranscriptApi.list_transcripts(video_id)
            return True
        except (TranscriptsDisabled, NoTranscriptFound):
            return False
