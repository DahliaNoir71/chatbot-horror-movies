"""YouTube video to TMDB film matcher.

Matches YouTube videos to films in database using
fuzzy title matching and confidence scoring.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import TypedDict

from rapidfuzz import fuzz, process

from src.etl.types import FilmMatchCandidate, FilmMatchResult
from src.etl.utils.logger import setup_logger


class VideoData(TypedDict, total=False):
    """Video data structure for batch matching."""

    title: str
    channel_handle: str | None
    video_db_id: int


class FilmData(TypedDict, total=False):
    """Film data structure from database."""

    id: int
    title: str
    release_date: date | str | None


@dataclass(frozen=True)
class ParsedVideoTitle:
    """Parsed film reference from video title.

    Attributes:
        film_title: Extracted film title.
        year: Extracted year (if found).
        confidence: Parsing confidence (0-1).
        original: Original video title.
    """

    film_title: str
    year: int | None
    confidence: float
    original: str


@dataclass(frozen=True)
class MatchResult:
    """Result of video-film matching.

    Attributes:
        success: Whether match was found.
        film_id: Matched film database ID.
        score: Match confidence score (0-1).
        method: Matching method used.
        film_title: Matched film title.
    """

    success: bool
    film_id: int | None
    score: float
    method: str
    film_title: str | None


class YouTubeMatcher:
    """Matches YouTube videos to TMDB films.

    Uses fuzzy title matching with year validation
    and channel trust scoring.

    Attributes:
        min_score: Minimum match score threshold.
        trusted_channels: Channel handles with trust bonus.
    """

    # Score thresholds
    _MIN_SCORE_DEFAULT = 0.70
    _EXACT_MATCH_THRESHOLD = 0.95
    _HIGH_CONFIDENCE_THRESHOLD = 0.85

    # Score bonuses
    _YEAR_MATCH_BONUS = 0.10
    _TRUSTED_CHANNEL_BONUS = 0.05

    # Common patterns in video titles to remove
    _NOISE_PATTERNS = [
        # Pipe suffix (e.g., "Title | Channel Name")
        r"\s*\|\s*.*$",
        # Review suffix variations
        r"\s*-\s*(?:movie\s+)?review.*$",
        # Critique suffix variations
        r"\s*-\s*(?:film\s+)?critique.*$",
        # Analysis suffix variations
        r"\s*-\s*(?:horror\s+)?analysis.*$",
        # Review/critique prefix
        r"^\s*(?:review|critique|avis)\s*[:|-]\s*",
        # Spoiler markers in parentheses
        r"\s*\((?:spoiler[s]?|no spoiler[s]?)\).*$",
        # Bracketed content
        r"\s*\[.*?\]\s*",
        # Hashtags
        r"\s*#\w+",
    ]

    # Year extraction pattern
    _YEAR_PATTERN = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\b")

    def __init__(
        self,
        min_score: float = _MIN_SCORE_DEFAULT,
        trusted_channels: list[str] | None = None,
    ) -> None:
        """Initialize matcher.

        Args:
            min_score: Minimum score to accept match.
            trusted_channels: Channel handles with bonus.
        """
        self._logger = setup_logger("etl.youtube.matcher")
        self._min_score = min_score
        self._trusted_channels = set(trusted_channels or [])

        self._logger.info(
            f"Matcher initialized (min_score={min_score:.2f}, "
            f"trusted_channels={len(self._trusted_channels)})"
        )

    # -------------------------------------------------------------------------
    # Main Matching
    # -------------------------------------------------------------------------

    def match_video(
        self,
        video_title: str,
        candidates: list[FilmMatchCandidate],
        channel_handle: str | None = None,
    ) -> MatchResult:
        """Match a video to the best film candidate.

        Args:
            video_title: YouTube video title.
            candidates: List of film candidates from database.
            channel_handle: Optional channel for trust bonus.

        Returns:
            MatchResult with best match or failure.
        """
        self._logger.debug(f"Matching: '{video_title[:60]}...'")

        if not candidates:
            return self._no_match("No candidates provided")

        parsed = self.parse_video_title(video_title)
        if not parsed.film_title:
            return self._no_match("Could not parse film title")

        best = self._find_best_match(parsed, candidates, channel_handle)

        if best.success:
            self._logger.debug(
                f"Match found: '{best.film_title}' (score={best.score:.2f}, method={best.method})"
            )

        return best

    def match_videos_batch(
        self,
        videos: list[VideoData],
        candidates: list[FilmMatchCandidate],
    ) -> list[FilmMatchResult]:
        """Match multiple videos to films.

        Args:
            videos: List of video dicts with title, youtube_id, channel.
            candidates: List of film candidates.

        Returns:
            List of successful match results.
        """
        self._logger.info(
            f"Batch matching: {len(videos)} videos against {len(candidates)} candidates"
        )

        results: list[FilmMatchResult] = []
        match_count = 0

        for video in videos:
            match = self.match_video(
                video_title=video.get("title", ""),
                candidates=candidates,
                channel_handle=video.get("channel_handle"),
            )

            if match.success and match.film_id is not None:
                match_count += 1
                results.append(
                    FilmMatchResult(
                        film_id=match.film_id,
                        video_id=video.get("video_db_id", 0),
                        match_score=match.score,
                        match_method=match.method,
                        matched_title=match.film_title or "",
                    )
                )

        success_rate = (match_count / len(videos) * 100) if videos else 0
        self._logger.info(
            f"Batch complete: {match_count}/{len(videos)} matched ({success_rate:.1f}%)"
        )

        return results

    # -------------------------------------------------------------------------
    # Title Parsing
    # -------------------------------------------------------------------------

    def parse_video_title(self, title: str) -> ParsedVideoTitle:
        """Parse film reference from video title.

        Extracts film title and optional year from
        video title, removing noise patterns.

        Args:
            title: Raw YouTube video title.

        Returns:
            ParsedVideoTitle with extracted data.
        """
        cleaned = self._clean_title(title)
        year = self._extract_year(cleaned)
        film_title = self._remove_year(cleaned, year)
        film_title = self._final_clean(film_title)

        confidence = self._calculate_parse_confidence(title, film_title, year)

        self._logger.debug(
            f"Parsed: '{title[:40]}...' -> '{film_title}' "
            f"(year={year}, confidence={confidence:.2f})"
        )

        return ParsedVideoTitle(
            film_title=film_title,
            year=year,
            confidence=confidence,
            original=title,
        )

    def _clean_title(self, title: str) -> str:
        """Remove noise patterns from title.

        Args:
            title: Raw title.

        Returns:
            Cleaned title.
        """
        cleaned = title.strip()

        for pattern in self._NOISE_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        return cleaned.strip()

    def _extract_year(self, text: str) -> int | None:
        """Extract year from text.

        Args:
            text: Text containing possible year.

        Returns:
            Extracted year or None.
        """
        matches = self._YEAR_PATTERN.findall(text)
        if matches:
            # Prefer year in parentheses or last occurrence
            return int(matches[-1])
        return None

    @staticmethod
    def _remove_year(text: str, year: int | None) -> str:
        """Remove year from text.

        Args:
            text: Text with year.
            year: Year to remove.

        Returns:
            Text without year.
        """
        if year is None:
            return text

        # Remove year with optional parentheses
        year_str = str(year)
        patterns = [
            r"\s*[(]" + year_str + r"[)]\s*",
            r"\s*" + year_str + r"\s*",
        ]

        result = text
        for pattern in patterns:
            result = re.sub(pattern, " ", result)

        return result.strip()

    @staticmethod
    def _final_clean(title: str) -> str:
        """Final cleanup of film title.

        Args:
            title: Partially cleaned title.

        Returns:
            Final cleaned title.
        """
        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", title)
        # Remove trailing punctuation
        cleaned = re.sub(r"[:\-,]+$", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def _calculate_parse_confidence(
        original: str,
        parsed: str,
        year: int | None,
    ) -> float:
        """Calculate parsing confidence.

        Args:
            original: Original title.
            parsed: Parsed film title.
            year: Extracted year.

        Returns:
            Confidence score 0-1.
        """
        if not parsed:
            return 0.0

        confidence = 0.5
        # Length ratio check
        ratio = len(parsed) / len(original) if original else 0
        if 0.2 < ratio < 0.8:
            confidence += 0.2
        # Year found bonus
        if year:
            confidence += 0.2
        # Reasonable title length
        if 2 <= len(parsed.split()) <= 10:
            confidence += 0.1

        return min(confidence, 1.0)

    # -------------------------------------------------------------------------
    # Fuzzy Matching
    # -------------------------------------------------------------------------

    def _find_best_match(
        self,
        parsed: ParsedVideoTitle,
        candidates: list[FilmMatchCandidate],
        channel_handle: str | None,
    ) -> MatchResult:
        """Find best matching film from candidates.

        Args:
            parsed: Parsed video title.
            candidates: Film candidates.
            channel_handle: Optional channel for trust bonus.

        Returns:
            Best match result.
        """
        # Prepare candidate titles for matching
        title_map = self._build_title_map(candidates)

        self._logger.debug(f"Fuzzy matching '{parsed.film_title}' against {len(title_map)} titles")

        # Find best fuzzy match
        best_match = self._fuzzy_match(parsed.film_title, list(title_map.keys()))

        if not best_match:
            return self._no_match("No fuzzy match found")

        matched_title, base_score = best_match
        candidate = title_map[matched_title]

        self._logger.debug(
            f"Best fuzzy match: '{candidate['title']}' (base_score={base_score:.2f})"
        )

        # Calculate final score with bonuses
        final_score = self._calculate_final_score(
            base_score=base_score,
            parsed_year=parsed.year,
            candidate_year=candidate["year"],
            channel_handle=channel_handle,
        )

        # Check threshold
        if final_score < self._min_score:
            return self._no_match(f"Score {final_score:.2f} below threshold")

        method = self._determine_method(base_score, parsed.year, candidate["year"])

        return MatchResult(
            success=True,
            film_id=candidate["film_id"],
            score=final_score,
            method=method,
            film_title=candidate["title"],
        )

    def _build_title_map(
        self,
        candidates: list[FilmMatchCandidate],
    ) -> dict[str, FilmMatchCandidate]:
        """Build mapping from normalized titles to candidates.

        Args:
            candidates: Film candidates.

        Returns:
            Dict mapping title to candidate.
        """
        title_map: dict[str, FilmMatchCandidate] = {}

        for candidate in candidates:
            normalized = self._normalize_for_matching(candidate["title"])
            title_map[normalized] = candidate

        return title_map

    @staticmethod
    def _normalize_for_matching(title: str) -> str:
        """Normalize title for fuzzy matching.

        Args:
            title: Raw title.

        Returns:
            Normalized lowercase title.
        """
        # Lowercase and remove special chars
        normalized = title.lower()
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _fuzzy_match(
        self,
        query: str,
        choices: list[str],
    ) -> tuple[str, float] | None:
        """Perform fuzzy matching.

        Args:
            query: Query string.
            choices: List of choices to match against.

        Returns:
            Tuple of (matched_string, score) or None.
        """
        if not query or not choices:
            return None

        normalized_query = self._normalize_for_matching(query)

        result = process.extractOne(
            normalized_query,
            choices,
            scorer=fuzz.WRatio,
            score_cutoff=50,
        )

        if result:
            matched, score, _ = result
            return matched, score / 100.0

        return None

    # -------------------------------------------------------------------------
    # Score Calculation
    # -------------------------------------------------------------------------

    def _calculate_final_score(
        self,
        base_score: float,
        parsed_year: int | None,
        candidate_year: int | None,
        channel_handle: str | None,
    ) -> float:
        """Calculate final match score with bonuses.

        Args:
            base_score: Base fuzzy match score.
            parsed_year: Year from video title.
            candidate_year: Year of candidate film.
            channel_handle: Channel handle for trust bonus.

        Returns:
            Final score capped at 1.0.
        """
        score = base_score
        bonuses: list[str] = []

        # Year match bonus
        if self._years_match(parsed_year, candidate_year):
            score += self._YEAR_MATCH_BONUS
            bonuses.append(f"year(+{self._YEAR_MATCH_BONUS})")

        # Trusted channel bonus
        if self._is_trusted_channel(channel_handle):
            score += self._TRUSTED_CHANNEL_BONUS
            bonuses.append(f"trusted(+{self._TRUSTED_CHANNEL_BONUS})")

        final = min(score, 1.0)

        if bonuses:
            self._logger.debug(
                f"Score calculation: {base_score:.2f} + {', '.join(bonuses)} = {final:.2f}"
            )

        return final

    @staticmethod
    def _years_match(year1: int | None, year2: int | None) -> bool:
        """Check if years match (with 1 year tolerance).

        Args:
            year1: First year.
            year2: Second year.

        Returns:
            True if years match within tolerance.
        """
        if year1 is None or year2 is None:
            return False
        return abs(year1 - year2) <= 1

    def _is_trusted_channel(self, handle: str | None) -> bool:
        """Check if channel is trusted.

        Args:
            handle: Channel handle.

        Returns:
            True if trusted.
        """
        if not handle:
            return False
        return handle.lstrip("@") in self._trusted_channels

    def _determine_method(
        self,
        base_score: float,
        parsed_year: int | None,
        candidate_year: int | None,
    ) -> str:
        """Determine match method label.

        Args:
            base_score: Base fuzzy score.
            parsed_year: Parsed year from video.
            candidate_year: Film candidate year.

        Returns:
            Method label string.
        """
        if base_score >= self._EXACT_MATCH_THRESHOLD:
            method = "title_exact"
        elif base_score >= self._HIGH_CONFIDENCE_THRESHOLD:
            method = "title_high"
        else:
            method = "title_fuzzy"

        if self._years_match(parsed_year, candidate_year):
            method += "_year"

        return method

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _no_match(self, reason: str) -> MatchResult:
        """Create no-match result.

        Args:
            reason: Reason for no match.

        Returns:
            Failed match result.
        """
        self._logger.debug(f"No match: {reason}")
        return MatchResult(
            success=False,
            film_id=None,
            score=0.0,
            method="none",
            film_title=None,
        )

    # -------------------------------------------------------------------------
    # Candidate Loading
    # -------------------------------------------------------------------------

    def build_candidates_from_db(
        self,
        films: list[FilmData],
    ) -> list[FilmMatchCandidate]:
        """Build candidate list from database films.

        Args:
            films: List of film dicts from database.

        Returns:
            List of FilmMatchCandidate.
        """
        self._logger.info(f"Building candidates from {len(films)} films")

        candidates: list[FilmMatchCandidate] = []

        for film in films:
            year = self._extract_year_from_date(film.get("release_date"))

            candidates.append(
                FilmMatchCandidate(
                    film_id=film["id"],
                    title=film["title"],
                    year=year,
                    score=0.0,
                )
            )

        with_year = sum(1 for c in candidates if c["year"] is not None)
        self._logger.debug(f"Candidates built: {len(candidates)} total, {with_year} with year")

        return candidates

    @staticmethod
    def _extract_year_from_date(date_value: date | str | None) -> int | None:
        """Extract year from date value.

        Args:
            date_value: Date object or string (YYYY-MM-DD format).

        Returns:
            Year integer or None.
        """
        if date_value is None:
            return None

        if hasattr(date_value, "year"):
            return date_value.year

        # Handle string format - combined logic to reduce return count
        match = re.match(r"(\d{4})", date_value) if isinstance(date_value, str) else None
        return int(match.group(1)) if match else None

    # -------------------------------------------------------------------------
    # Trust Management
    # -------------------------------------------------------------------------

    def add_trusted_channel(self, handle: str) -> None:
        """Add channel to trusted list.

        Args:
            handle: Channel handle.
        """
        clean_handle = handle.lstrip("@")
        self._trusted_channels.add(clean_handle)
        self._logger.info(
            f"Added trusted channel: {clean_handle} (total: {len(self._trusted_channels)})"
        )

    def remove_trusted_channel(self, handle: str) -> None:
        """Remove channel from trusted list.

        Args:
            handle: Channel handle.
        """
        clean_handle = handle.lstrip("@")
        self._trusted_channels.discard(clean_handle)
        self._logger.info(
            f"Removed trusted channel: {clean_handle} (total: {len(self._trusted_channels)})"
        )

    def set_min_score(self, score: float) -> None:
        """Update minimum match score.

        Args:
            score: New minimum score (0-1).
        """
        old_score = self._min_score
        self._min_score = max(0.0, min(1.0, score))
        self._logger.info(f"Min score updated: {old_score:.2f} -> {self._min_score:.2f}")
