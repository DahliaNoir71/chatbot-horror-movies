"""Film deduplication module.

Detects and removes duplicate films using tmdb_id,
imdb_id, and fuzzy title matching with year tolerance.
"""

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from src.etl.aggregation.schemas import AggregatedFilm

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

SIMILARITY_THRESHOLD = 0.90
"""Minimum title similarity ratio for fuzzy matching."""

YEAR_TOLERANCE = 1
"""Maximum year difference for considering films as duplicates."""


# =============================================================================
# DEDUPLICATION STATISTICS
# =============================================================================


@dataclass
class DeduplicationStats:
    """Statistics for deduplication operations.

    Attributes:
        total_input: Total films before deduplication.
        duplicates_tmdb_id: Duplicates found by tmdb_id.
        duplicates_imdb_id: Duplicates found by imdb_id.
        duplicates_fuzzy: Duplicates found by fuzzy matching.
        total_output: Films after deduplication.
    """

    total_input: int = 0
    duplicates_tmdb_id: int = 0
    duplicates_imdb_id: int = 0
    duplicates_fuzzy: int = 0
    total_output: int = 0

    @property
    def total_duplicates(self) -> int:
        """Calculate total duplicates found."""
        return self.duplicates_tmdb_id + self.duplicates_imdb_id + self.duplicates_fuzzy

    def log_summary(self) -> None:
        """Log deduplication statistics summary."""
        logger.info(
            "Deduplication: %d -> %d films (-%d duplicates: tmdb=%d, imdb=%d, fuzzy=%d)",
            self.total_input,
            self.total_output,
            self.total_duplicates,
            self.duplicates_tmdb_id,
            self.duplicates_imdb_id,
            self.duplicates_fuzzy,
        )


# =============================================================================
# SEEN FILMS TRACKER
# =============================================================================


@dataclass
class SeenFilmsTracker:
    """Tracks seen films for deduplication.

    Maintains indices by tmdb_id, imdb_id, and normalized
    title+year for efficient duplicate detection.

    Attributes:
        by_tmdb_id: Set of seen tmdb_ids.
        by_imdb_id: Set of seen imdb_ids.
        by_title_year: Dict mapping normalized title to year.
    """

    by_tmdb_id: set[int] = field(default_factory=set)
    by_imdb_id: set[str] = field(default_factory=set)
    by_title_year: dict[str, int] = field(default_factory=dict)

    def add(self, film: AggregatedFilm) -> None:
        """Register film as seen.

        Args:
            film: Film to register.
        """
        self.by_tmdb_id.add(film.tmdb_id)
        if film.imdb_id:
            self.by_imdb_id.add(film.imdb_id)
        if film.year:
            normalized_title = self._normalize_title(film.title)
            self.by_title_year[normalized_title] = film.year

    def has_tmdb_id(self, tmdb_id: int) -> bool:
        """Check if tmdb_id was already seen.

        Args:
            tmdb_id: TMDB identifier to check.

        Returns:
            True if already seen.
        """
        return tmdb_id in self.by_tmdb_id

    def has_imdb_id(self, imdb_id: str | None) -> bool:
        """Check if imdb_id was already seen.

        Args:
            imdb_id: IMDB identifier to check.

        Returns:
            True if already seen.
        """
        if not imdb_id:
            return False
        return imdb_id in self.by_imdb_id

    def find_similar_title(self, title: str, year: int | None) -> str | None:
        """Find similar title in seen films.

        Args:
            title: Title to search for.
            year: Release year for filtering.

        Returns:
            Similar title if found, None otherwise.
        """
        if not year:
            return None

        normalized = self._normalize_title(title)

        for seen_title, seen_year in self.by_title_year.items():
            if self._is_year_match(year, seen_year) and self._is_title_similar(
                normalized, seen_title
            ):
                return seen_title

        return None

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title for comparison.

        Args:
            title: Original title.

        Returns:
            Lowercase stripped title.
        """
        return title.lower().strip()

    @staticmethod
    def _is_year_match(year1: int, year2: int) -> bool:
        """Check if years are within tolerance.

        Args:
            year1: First year.
            year2: Second year.

        Returns:
            True if within YEAR_TOLERANCE.
        """
        return abs(year1 - year2) <= YEAR_TOLERANCE

    @staticmethod
    def _is_title_similar(title1: str, title2: str) -> bool:
        """Check if titles are similar using SequenceMatcher.

        Args:
            title1: First normalized title.
            title2: Second normalized title.

        Returns:
            True if similarity >= SIMILARITY_THRESHOLD.
        """
        ratio = SequenceMatcher(None, title1, title2).ratio()
        return ratio >= SIMILARITY_THRESHOLD


# =============================================================================
# DEDUPLICATOR
# =============================================================================


class Deduplicator:
    """Removes duplicate films from aggregated dataset.

    Uses three-stage detection:
    1. Exact tmdb_id match
    2. Exact imdb_id match
    3. Fuzzy title + year match

    Attributes:
        stats: Deduplication statistics.
    """

    def __init__(self) -> None:
        """Initialize deduplicator with empty state."""
        self.stats = DeduplicationStats()
        self._tracker = SeenFilmsTracker()

    # =========================================================================
    # Public API
    # =========================================================================

    def deduplicate(self, films: list[AggregatedFilm]) -> list[AggregatedFilm]:
        """Remove duplicate films from list.

        Args:
            films: List of aggregated films to deduplicate.

        Returns:
            List with duplicates removed.
        """
        self._reset_state()
        self.stats.total_input = len(films)

        unique_films: list[AggregatedFilm] = []

        for film in films:
            if self._is_duplicate(film):
                continue
            self._tracker.add(film)
            unique_films.append(film)

        self.stats.total_output = len(unique_films)
        self.stats.log_summary()

        return unique_films

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _reset_state(self) -> None:
        """Reset internal state for new operation."""
        self.stats = DeduplicationStats()
        self._tracker = SeenFilmsTracker()

    def _is_duplicate(self, film: AggregatedFilm) -> bool:
        """Check if film is a duplicate.

        Args:
            film: Film to check.

        Returns:
            True if duplicate detected.
        """
        return (
            self._check_tmdb_duplicate(film)
            or self._check_imdb_duplicate(film)
            or self._check_fuzzy_duplicate(film)
        )

    def _check_tmdb_duplicate(self, film: AggregatedFilm) -> bool:
        """Check for tmdb_id duplicate.

        Args:
            film: Film to check.

        Returns:
            True if tmdb_id already seen.
        """
        if self._tracker.has_tmdb_id(film.tmdb_id):
            self.stats.duplicates_tmdb_id += 1
            logger.debug("Duplicate (tmdb_id): %s", film.title)
            return True
        return False

    def _check_imdb_duplicate(self, film: AggregatedFilm) -> bool:
        """Check for imdb_id duplicate.

        Args:
            film: Film to check.

        Returns:
            True if imdb_id already seen.
        """
        if self._tracker.has_imdb_id(film.imdb_id):
            self.stats.duplicates_imdb_id += 1
            logger.debug("Duplicate (imdb_id): %s", film.title)
            return True
        return False

    def _check_fuzzy_duplicate(self, film: AggregatedFilm) -> bool:
        """Check for fuzzy title+year duplicate.

        Args:
            film: Film to check.

        Returns:
            True if similar title found within year tolerance.
        """
        similar = self._tracker.find_similar_title(film.title, film.year)
        if similar:
            self.stats.duplicates_fuzzy += 1
            logger.debug("Duplicate (fuzzy): '%s' ~ '%s'", film.title, similar)
            return True
        return False
