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
        self._logger.info(f"TranscriptExtractor initialized with languages: {self._languages}")

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
        self._logger.info(f"Extracting transcript for video: {video_id}")

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            self._logger.debug(f"Transcript list retrieved for {video_id}")
            result = self._extract_best_transcript(video_id, transcript_list)

            if result.success:
                self._logger.info(
                    f"Transcript extracted successfully: {video_id} "
                    f"({result.language}, {result.word_count} words, "
                    f"{'generated' if result.is_generated else 'manual'})"
                )
            else:
                self._logger.warning(f"Transcript extraction failed for {video_id}: {result.error}")

            return result

        except self._NO_TRANSCRIPT_ERRORS as e:
            error_msg = f"No transcript available: {type(e).__name__}"
            self._logger.warning(f"{error_msg} for video {video_id}")
            return self._create_error_result(error_msg)
        except Exception as e:
            self._logger.error(f"Transcript extraction failed for {video_id}: {e}")
            return self._create_error_result(str(e))

    def _extract_best_transcript(
        self,
        video_id: str,
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
        self._logger.debug(f"Finding best transcript for {video_id}")

        # Try manual transcript first
        self._logger.debug("Attempting to find manual transcript...")
        manual = self._try_manual_transcript(video_id, transcript_list)
        if manual:
            self._logger.debug(f"Manual transcript found for {video_id}")
            return manual

        # Fall back to auto-generated
        self._logger.debug("Manual transcript not found, trying auto-generated...")
        generated = self._try_generated_transcript(video_id, transcript_list)
        if generated:
            self._logger.debug(f"Auto-generated transcript found for {video_id}")
            return generated

        self._logger.warning(f"No suitable transcript found for {video_id}")
        return self._create_error_result("No suitable transcript found")

    def _try_manual_transcript(
        self,
        video_id: str,
        transcript_list: object,
    ) -> TranscriptResult | None:
        """Try to get manual transcript in preferred languages.

        Args:
            video_id: YouTube video ID.
            transcript_list: TranscriptList from API.

        Returns:
            TranscriptResult or None if not available.
        """
        try:
            transcript = transcript_list.find_manually_created_transcript(self._languages)
            self._logger.debug(
                f"Found manual transcript for {video_id} in language: {transcript.language_code}"
            )
            return self._fetch_and_build_result(video_id, transcript, is_generated=False)
        except NoTranscriptFound:
            self._logger.debug(f"No manual transcript found for {video_id}")
            return None

    def _try_generated_transcript(
        self,
        video_id: str,
        transcript_list: object,
    ) -> TranscriptResult | None:
        """Try to get auto-generated transcript.

        Args:
            video_id: YouTube video ID.
            transcript_list: TranscriptList from API.

        Returns:
            TranscriptResult or None if not available.
        """
        try:
            transcript = transcript_list.find_generated_transcript(self._languages)
            self._logger.debug(
                f"Found auto-generated transcript for {video_id} in language: {transcript.language_code}"
            )
            return self._fetch_and_build_result(video_id, transcript, is_generated=True)
        except NoTranscriptFound:
            self._logger.debug(f"No auto-generated transcript found for {video_id}")
            return None

    def _fetch_and_build_result(
        self,
        video_id: str,
        transcript: object,
        is_generated: bool,
    ) -> TranscriptResult:
        """Fetch transcript data and build result.

        Args:
            video_id: YouTube video ID.
            transcript: Transcript object from API.
            is_generated: Whether auto-generated.

        Returns:
            TranscriptResult with full text.
        """
        self._logger.debug(f"Fetching transcript segments for {video_id}")
        segments = transcript.fetch()

        self._logger.debug(f"Processing {len(segments)} transcript segments for {video_id}")
        full_text = self._join_segments(segments)
        language = getattr(transcript, "language_code", "en")
        word_count = self._count_words(full_text)

        self._logger.debug(
            f"Transcript processed: {video_id} -> {word_count} words, "
            f"language: {language}, generated: {is_generated}"
        )

        return TranscriptResult(
            success=True,
            transcript=full_text,
            language=language,
            is_generated=is_generated,
            word_count=word_count,
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
        joined_text = " ".join(filter(None, texts))

        if not joined_text:
            self._logger.warning("All transcript segments were empty after cleaning")

        return joined_text

    def _clean_segment_text(self, text: str) -> str:
        """Clean individual segment text.

        Removes music indicators, normalizes whitespace.

        Args:
            text: Raw segment text.

        Returns:
            Cleaned text.
        """
        if not text:
            return ""

        original = text
        cleaned = text.strip()
        cleaned = self._remove_music_indicators(cleaned)
        cleaned = self._normalize_whitespace(cleaned)

        if original != cleaned:
            self._logger.debug(f"Segment cleaned: '{original[:50]}...' -> '{cleaned[:50]}...'")

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
        return len(text.split()) if text else 0

    # -------------------------------------------------------------------------
    # Result Helpers
    # -------------------------------------------------------------------------

    def _create_error_result(self, error: str) -> TranscriptResult:
        """Create error result.

        Args:
            error: Error message.

        Returns:
            TranscriptResult indicating failure.
        """
        self._logger.debug(f"Creating error result: {error}")
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
        if not video_ids:
            self._logger.warning("Empty video IDs list provided for batch extraction")
            return {}

        self._logger.info(f"Starting batch transcript extraction for {len(video_ids)} videos")
        results: dict[str, TranscriptResult] = {}

        for idx, video_id in enumerate(video_ids, 1):
            if idx % 10 == 0:
                self._logger.debug(f"Batch progress: {idx}/{len(video_ids)}")

            results[video_id] = self.extract(video_id)
            self._log_extraction_result(video_id, results[video_id])

        # Calculate statistics
        success_count = sum(1 for r in results.values() if r.success)
        success_rate = (success_count / len(video_ids) * 100) if video_ids else 0

        self._logger.info(
            f"Batch extraction complete: {success_count}/{len(video_ids)} succeeded "
            f"({success_rate:.1f}%)"
        )

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
                f"Transcript extracted: {video_id} ({result.language}, "
                f"{result.word_count} words, {'generated' if result.is_generated else 'manual'})"
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

    # -------------------------------------------------------------------------
    # Language Management
    # -------------------------------------------------------------------------

    def get_languages(self) -> list[str]:
        """Get current preferred languages list.

        Returns:
            List of language codes in priority order.
        """
        return self._languages.copy()

    def set_languages(self, languages: list[str]) -> None:
        """Update preferred languages.

        Args:
            languages: New language priority list.
        """
        old_languages = self._languages
        self._languages = languages.copy()

        self._logger.info(f"Updated languages: {old_languages} -> {self._languages}")

    def add_language(self, language: str, priority: int | None = None) -> None:
        """Add a language to preferred list.

        Args:
            language: Language code to add.
            priority: Position in list (None for end).
        """
        if language in self._languages:
            self._logger.debug(f"Language already in list: {language}")
            return

        if priority is None or priority >= len(self._languages):
            self._languages.append(language)
        else:
            self._languages.insert(priority, language)

        self._logger.info(f"Added language: {language} at position {priority or 'end'}")
