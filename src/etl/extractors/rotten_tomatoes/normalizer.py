"""Rotten Tomatoes data normalizer.

Transforms scraped RT data into normalized format
for database insertion.
"""

import logging
from typing import Any

from src.etl.types import NormalizedRTScoreData
from src.etl.utils.logger import setup_logger


class RTNormalizer:
    """Normalizes Rotten Tomatoes scraped data.

    Transforms raw scraped data into NormalizedRTScoreData
    ready for database insertion.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize normalizer.

        Args:
            logger: Optional logger instance.
        """
        self._logger = setup_logger("etl.rt.normalizer")

    def normalize(
        self,
        raw_data: dict[str, Any],
        film_id: int,
    ) -> NormalizedRTScoreData | None:
        """Normalize scraped RT data for database.

        Args:
            raw_data: Raw scraped data dict.
            film_id: Database film ID to associate.

        Returns:
            NormalizedRTScoreData or None if invalid.
        """
        if not raw_data:
            return None

        # Must have at least one score
        has_tomatometer = raw_data.get("tomatometer_score") is not None
        has_audience = raw_data.get("audience_score") is not None

        if not has_tomatometer and not has_audience:
            self._logger.debug(f"No scores for film_id={film_id}")
            return None

        return NormalizedRTScoreData(
            film_id=film_id,
            tomatometer_score=self._safe_int(raw_data.get("tomatometer_score")),
            tomatometer_state=self._normalize_state(raw_data.get("tomatometer_state")),
            critics_count=raw_data.get("critics_count", 0),
            critics_average_rating=self._safe_float(raw_data.get("critics_average_rating")),
            audience_score=self._safe_int(raw_data.get("audience_score")),
            audience_state=self._normalize_state(raw_data.get("audience_state")),
            audience_count=raw_data.get("audience_count", 0),
            audience_average_rating=self._safe_float(raw_data.get("audience_average_rating")),
            critics_consensus=self._clean_consensus(raw_data.get("critics_consensus")),
            rt_url=raw_data.get("rt_url"),
            rt_rating=raw_data.get("rt_rating"),
        )

    def normalize_batch(
        self,
        results: list[tuple[int, dict[str, Any]]],
    ) -> list[NormalizedRTScoreData]:
        """Normalize multiple RT results.

        Args:
            results: List of (film_id, raw_data) tuples.

        Returns:
            List of normalized data (skips invalid).
        """
        normalized = []
        for film_id, raw_data in results:
            result = self.normalize(raw_data, film_id)
            if result:
                normalized.append(result)
        return normalized

    # -------------------------------------------------------------------------
    # Validation & Cleaning
    # -------------------------------------------------------------------------

    @staticmethod
    def _safe_int(value: int | float | str | None) -> int | None:
        """Safely convert value to int.

        Args:
            value: Value to convert (int, float, str or None).

        Returns:
            Int value or None.
        """
        if value is None:
            return None
        try:
            result = int(value)
            return result if 0 <= result <= 100 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(value: int | float | str | None) -> float | None:
        """Safely convert value to float.

        Args:
            value: Value to convert (int, float, str or None).

        Returns:
            Float value or None.
        """
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _normalize_state(state: str | None) -> str | None:
        """Normalize score state string.

        Args:
            state: Raw state string.

        Returns:
            Normalized state or None.
        """
        if not state:
            return None

        state_lower = state.lower().strip()

        # Map to standard states
        state_map = {
            "fresh": "fresh",
            "certified_fresh": "certified_fresh",
            "certified-fresh": "certified_fresh",
            "rotten": "rotten",
            "positive": "fresh",
            "negative": "rotten",
            "upright": "fresh",
            "spilled": "rotten",
        }

        return state_map.get(state_lower, state_lower)

    @staticmethod
    def _clean_consensus(consensus: str | None) -> str | None:
        """Clean critics consensus text.

        Args:
            consensus: Raw consensus text.

        Returns:
            Cleaned consensus or None.
        """
        if not consensus:
            return None

        # Remove leading labels
        text = consensus.strip()
        prefixes = [
            "Critics Consensus:",
            "Critics Consensus",
            "Critic's Consensus:",
        ]
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()

        # Skip placeholder text
        if "no consensus yet" in text.lower():
            return None

        return text if len(text) > 20 else None

    # -------------------------------------------------------------------------
    # Derived Properties
    # -------------------------------------------------------------------------

    @staticmethod
    def is_certified_fresh(data: NormalizedRTScoreData) -> bool:
        """Check if film is Certified Fresh.

        Args:
            data: Normalized RT data.

        Returns:
            True if Certified Fresh.
        """
        return data.get("tomatometer_state") == "certified_fresh"

    @staticmethod
    def is_fresh(data: NormalizedRTScoreData) -> bool:
        """Check if film is Fresh (60%+).

        Args:
            data: Normalized RT data.

        Returns:
            True if Fresh or Certified Fresh.
        """
        score = data.get("tomatometer_score")
        if score is None:
            return False
        return score >= 60

    @staticmethod
    def is_rotten(data: NormalizedRTScoreData) -> bool:
        """Check if film is Rotten (<60%).

        Args:
            data: Normalized RT data.

        Returns:
            True if Rotten.
        """
        score = data.get("tomatometer_score")
        if score is None:
            return False
        return score < 60
