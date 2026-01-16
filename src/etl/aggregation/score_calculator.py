"""Aggregated score calculator for films.

Computes weighted score from multiple sources:
TMDB (25%), Rotten Tomatoes (30%), IMDB (30%), Kaggle (15%).
"""

import logging
from dataclasses import dataclass

from src.etl.aggregation.schemas import AggregatedFilm

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS - SCORE WEIGHTS
# =============================================================================

WEIGHT_TMDB = 0.25
"""TMDB vote_average weight (25%)."""

WEIGHT_RT = 0.30
"""Rotten Tomatoes tomatometer weight (30%)."""

WEIGHT_IMDB = 0.30
"""IMDB rating weight (30%)."""

WEIGHT_KAGGLE = 0.15
"""Kaggle rating weight (15%)."""

RT_SCALE_FACTOR = 10.0
"""Factor to convert RT score (0-100) to 0-10 scale."""

MIN_SCORE = 0.0
"""Minimum valid score."""

MAX_SCORE = 10.0
"""Maximum valid score."""


# =============================================================================
# SCORE STATISTICS
# =============================================================================


@dataclass
class ScoreStats:
    """Statistics for score calculation.

    Attributes:
        total_films: Total films processed.
        with_tmdb: Films with TMDB score.
        with_rt: Films with RT score.
        with_imdb: Films with IMDB score.
        with_kaggle: Films with Kaggle score.
        avg_score: Average aggregated score.
    """

    total_films: int = 0
    with_tmdb: int = 0
    with_rt: int = 0
    with_imdb: int = 0
    with_kaggle: int = 0
    score_sum: float = 0.0

    @property
    def avg_score(self) -> float:
        """Calculate average aggregated score."""
        if self.total_films == 0:
            return 0.0
        return round(self.score_sum / self.total_films, 2)

    def log_summary(self) -> None:
        """Log score calculation statistics."""
        logger.info(
            "Score calculation: %d films, avg=%.2f (TMDB=%d, RT=%d, IMDB=%d, Kaggle=%d)",
            self.total_films,
            self.avg_score,
            self.with_tmdb,
            self.with_rt,
            self.with_imdb,
            self.with_kaggle,
        )


# =============================================================================
# INDIVIDUAL SCORE EXTRACTORS
# =============================================================================


@dataclass
class ScoreComponent:
    """Single score component with weight.

    Attributes:
        value: Normalized score (0-10).
        weight: Weight for aggregation.
    """

    value: float
    weight: float

    @property
    def weighted_value(self) -> float:
        """Calculate weighted contribution."""
        return self.value * self.weight


class ScoreExtractor:
    """Extracts and normalizes scores from film data."""

    @staticmethod
    def get_tmdb_score(film: AggregatedFilm) -> ScoreComponent | None:
        """Extract TMDB score if available.

        Args:
            film: Film with potential TMDB data.

        Returns:
            ScoreComponent or None if not available.
        """
        if film.vote_average <= MIN_SCORE:
            return None
        return ScoreComponent(value=film.vote_average, weight=WEIGHT_TMDB)

    @staticmethod
    def get_rt_score(film: AggregatedFilm) -> ScoreComponent | None:
        """Extract RT tomatometer score if available.

        Args:
            film: Film with potential RT data.

        Returns:
            ScoreComponent or None if not available.
        """
        if film.tomatometer_score is None:
            return None
        normalized = film.tomatometer_score / RT_SCALE_FACTOR
        return ScoreComponent(value=normalized, weight=WEIGHT_RT)

    @staticmethod
    def get_imdb_score(film: AggregatedFilm) -> ScoreComponent | None:
        """Extract IMDB rating if available.

        Args:
            film: Film with potential IMDB data.

        Returns:
            ScoreComponent or None if not available.
        """
        if film.imdb_rating is None:
            return None
        return ScoreComponent(value=film.imdb_rating, weight=WEIGHT_IMDB)

    @staticmethod
    def get_kaggle_score(film: AggregatedFilm) -> ScoreComponent | None:
        """Extract Kaggle rating if available.

        Args:
            film: Film with potential Kaggle data.

        Returns:
            ScoreComponent or None if not available.
        """
        if film.kaggle_rating is None:
            return None
        return ScoreComponent(value=film.kaggle_rating, weight=WEIGHT_KAGGLE)


# =============================================================================
# SCORE CALCULATOR
# =============================================================================


class ScoreCalculator:
    """Calculates weighted aggregated scores for films.

    Uses available scores from each source with dynamic
    weight normalization when sources are missing.

    Attributes:
        stats: Calculation statistics.
    """

    def __init__(self) -> None:
        """Initialize calculator with empty statistics."""
        self.stats = ScoreStats()
        self._extractor = ScoreExtractor()

    # =========================================================================
    # Public API
    # =========================================================================

    def calculate_scores(self, films: list[AggregatedFilm]) -> list[AggregatedFilm]:
        """Calculate aggregated scores for all films.

        Args:
            films: Films to process.

        Returns:
            Films with updated aggregated_score field.
        """
        self._reset_state()

        for film in films:
            score = self._calculate_single_score(film)
            film.aggregated_score = score
            self._update_stats(film, score)

        self.stats.log_summary()
        return films

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _reset_state(self) -> None:
        """Reset statistics for new calculation."""
        self.stats = ScoreStats()

    def _calculate_single_score(self, film: AggregatedFilm) -> float:
        """Calculate aggregated score for single film.

        Args:
            film: Film to score.

        Returns:
            Weighted aggregated score (0-10).
        """
        components = self._collect_components(film)
        if not components:
            return MIN_SCORE
        return self._compute_weighted_average(components)

    def _collect_components(self, film: AggregatedFilm) -> list[ScoreComponent]:
        """Collect all available score components.

        Args:
            film: Film to extract scores from.

        Returns:
            List of available score components.
        """
        components: list[ScoreComponent] = []

        tmdb = self._extractor.get_tmdb_score(film)
        if tmdb:
            components.append(tmdb)

        rt = self._extractor.get_rt_score(film)
        if rt:
            components.append(rt)

        imdb = self._extractor.get_imdb_score(film)
        if imdb:
            components.append(imdb)

        kaggle = self._extractor.get_kaggle_score(film)
        if kaggle:
            components.append(kaggle)

        return components

    @staticmethod
    def _compute_weighted_average(components: list[ScoreComponent]) -> float:
        """Compute normalized weighted average.

        Args:
            components: Available score components.

        Returns:
            Weighted average normalized to available weights.
        """
        total_weight = sum(c.weight for c in components)
        if total_weight <= MIN_SCORE:
            return MIN_SCORE

        weighted_sum = sum(c.weighted_value for c in components)
        score = weighted_sum / total_weight

        return round(min(score, MAX_SCORE), 2)

    def _update_stats(self, film: AggregatedFilm, score: float) -> None:
        """Update statistics after scoring a film.

        Args:
            film: Scored film.
            score: Calculated score.
        """
        self.stats.total_films += 1
        self.stats.score_sum += score

        if film.vote_average > MIN_SCORE:
            self.stats.with_tmdb += 1
        if film.tomatometer_score is not None:
            self.stats.with_rt += 1
        if film.imdb_rating is not None:
            self.stats.with_imdb += 1
        if film.kaggle_rating is not None:
            self.stats.with_kaggle += 1
