"""YouTube transcript extraction.

Extracts video transcripts using youtube-transcript-api
with language fallback and normalization.
"""

from dataclasses import dataclass

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)
from youtube_transcript_api._errors import NoTranscriptAvailable

from src.etl.types import YouTubeTranscriptData
from src.etl.utils.logger import setup_logger


@dataclass(frozen=True)
class TranscriptResult:
    """Result of transcript extraction.

    Attributes:
        success: Whether extraction succeeded.
        transcript: Full transcript text (empty if failed).
        language: Detected language code.
        is_generated: Whether auto-generated.
        word_count: Total word count.
        error: Error message if failed.
    """

    success: bool
    transcript: str
    language: str
    is_generated: bool
    word_count: int
    error: str | None = None


class TranscriptExtractor:
    """Extracts transcripts from YouTube videos.

    Supports multiple language fallbacks and handles
    auto-generated vs manual transcripts.

    Attributes:
        preferred_languages: Ordered list of preferred languages.
    """

    # Default language priority
    _DEFAULT_LANGUAGES = ["en", "en-US", "en-GB", "fr", "es", "de"]

    # Errors that indicate no transcript available
    _NO_TRANSCRIPT_ERRORS = (
        NoTranscriptFound,
        NoTranscriptAvailable,
        TranscriptsDisabled,
    )

    def __init__(
        self,
        preferred_languages: list[str] | None = None,
    ) -> None:
        """Initialize transcript extractor.

        Args:
            preferred_languages: Ordered language preferences.
        """
        self._logger = setup_logger("etl.youtube.transcript")
        self._languages = preferred_languages or self._DEFAULT_LANGUAGES

    # -------------------------------------------------------------------------
    # Main Extraction
    # -------------------------------------------------------------------------

    def extract(self, video_id: str) -> TranscriptResult:
        """Extract transcript for a video.

        Attempts manual transcripts first, then auto-generated.

        Args:
            video_id: YouTube video ID.

        Returns:
            TranscriptResult with transcript or error.
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            return self._extract_best_transcript(transcript_list)
        except self._NO_TRANSCRIPT_ERRORS as e:
            return self._create_error_result(f"No transcript: {type(e).__name__}")
        except Exception as e:
            self._logger.error(f"Transcript extraction failed for {video_id}: {e}")
            return self._create_error_result(str(e))

    def _extract_best_transcript(
        self,
        transcript_list: object,
    ) -> TranscriptResult:
        """Extract best available transcript.

        Priority: manual in preferred language > auto-generated.

        Args:
            video_id: YouTube video ID.
            transcript_list: TranscriptList from API.

        Returns:
            TranscriptResult with best transcript.
        """
        # Try manual transcript first
        manual = self._try_manual_transcript(transcript_list)
        if manual:
            return manual

        # Fall back to auto-generated
        generated = self._try_generated_transcript(transcript_list)
        if generated:
            return generated

        return self._create_error_result("No suitable transcript found")

    def _try_manual_transcript(
        self,
        transcript_list: object,
    ) -> TranscriptResult | None:
        """Try to get manual transcript in preferred languages.

        Args:
            transcript_list: TranscriptList from API.

        Returns:
            TranscriptResult or None if not available.
        """
        try:
            transcript = transcript_list.find_manually_created_transcript(self._languages)
            return self._fetch_and_build_result(transcript, is_generated=False)
        except NoTranscriptFound:
            return None

    def _try_generated_transcript(
        self,
        transcript_list: object,
    ) -> TranscriptResult | None:
        """Try to get auto-generated transcript.

        Args:
            transcript_list: TranscriptList from API.

        Returns:
            TranscriptResult or None if not available.
        """
        try:
            transcript = transcript_list.find_generated_transcript(self._languages)
            return self._fetch_and_build_result(transcript, is_generated=True)
        except NoTranscriptFound:
            return None

    def _fetch_and_build_result(
        self,
        transcript: object,
        is_generated: bool,
    ) -> TranscriptResult:
        """Fetch transcript data and build result.

        Args:
            transcript: Transcript object from API.
            is_generated: Whether auto-generated.

        Returns:
            TranscriptResult with full text.
        """
        segments = transcript.fetch()
        full_text = self._join_segments(segments)
        language = getattr(transcript, "language_code", "en")

        return TranscriptResult(
            success=True,
            transcript=full_text,
            language=language,
            is_generated=is_generated,
            word_count=self._count_words(full_text),
        )

    # -------------------------------------------------------------------------
    # Text Processing
    # -------------------------------------------------------------------------

    def _join_segments(self, segments: list[dict[str, str | float]]) -> str:
        """Join transcript segments into full text.

        Args:
            segments: List of segment dicts with 'text' key.

        Returns:
            Joined transcript text.
        """
        texts = [self._clean_segment_text(s.get("text", "")) for s in segments]
        return " ".join(filter(None, texts))

    def _clean_segment_text(self, text: str) -> str:
        """Clean individual segment text.

        Removes music indicators, normalizes whitespace.

        Args:
            text: Raw segment text.

        Returns:
            Cleaned text.
        """
        cleaned = text.strip()
        cleaned = self._remove_music_indicators(cleaned)
        cleaned = self._normalize_whitespace(cleaned)
        return cleaned

    @staticmethod
    def _remove_music_indicators(text: str) -> str:
        """Remove [Music], [Applause], etc. markers.

        Args:
            text: Text with possible markers.

        Returns:
            Text without markers.
        """
        import re

        return re.sub(r"\[[^]]*]", "", text)

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalize whitespace in text.

        Args:
            text: Text with irregular whitespace.

        Returns:
            Text with single spaces.
        """
        import re

        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _count_words(text: str) -> int:
        """Count words in text.

        Args:
            text: Full transcript text.

        Returns:
            Word count.
        """
        return len(text.split())

    # -------------------------------------------------------------------------
    # Result Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _create_error_result(error: str) -> TranscriptResult:
        """Create error result.

        Args:
            error: Error message.

        Returns:
            TranscriptResult indicating failure.
        """
        return TranscriptResult(
            success=False,
            transcript="",
            language="",
            is_generated=False,
            word_count=0,
            error=error,
        )

    # -------------------------------------------------------------------------
    # Batch Extraction
    # -------------------------------------------------------------------------

    def extract_batch(
        self,
        video_ids: list[str],
    ) -> dict[str, TranscriptResult]:
        """Extract transcripts for multiple videos.

        Args:
            video_ids: List of YouTube video IDs.

        Returns:
            Dict mapping video_id to TranscriptResult.
        """
        results: dict[str, TranscriptResult] = {}

        for video_id in video_ids:
            results[video_id] = self.extract(video_id)
            self._log_extraction_result(video_id, results[video_id])

        return results

    def _log_extraction_result(
        self,
        video_id: str,
        result: TranscriptResult,
    ) -> None:
        """Log extraction result.

        Args:
            video_id: YouTube video ID.
            result: Extraction result.
        """
        if result.success:
            self._logger.debug(
                f"Transcript extracted: {video_id} ({result.language}, {result.word_count} words)"
            )
        else:
            self._logger.debug(f"Transcript failed: {video_id} - {result.error}")

    # -------------------------------------------------------------------------
    # Normalization
    # -------------------------------------------------------------------------

    @staticmethod
    def to_normalized_data(
        video_id: str,
        result: TranscriptResult,
    ) -> YouTubeTranscriptData | None:
        """Convert result to normalized data format.

        Args:
            video_id: YouTube video ID.
            result: Transcript extraction result.

        Returns:
            Normalized data or None if extraction failed.
        """
        if not result.success:
            return None

        return YouTubeTranscriptData(
            youtube_id=video_id,
            transcript=result.transcript,
            language=result.language,
            is_generated=result.is_generated,
            word_count=result.word_count,
        )
