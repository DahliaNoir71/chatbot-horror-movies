"""Spark data normalizer.

Transforms raw Spark extracted data into normalized format
for aggregation with other sources.
"""

from src.etl.types.spark import SparkEnrichedMovie, SparkNormalized
from src.etl.utils.logger import setup_logger


class SparkNormalizer:
    """Normalizes Spark extracted data.

    Transforms SparkEnrichedMovie into SparkNormalized
    ready for aggregation pipelines.

    Attributes:
        SOURCE_NAME: Source identifier for normalized records.
    """

    SOURCE_NAME = "spark_kaggle"

    def __init__(self) -> None:
        """Initialize normalizer."""
        self._logger = setup_logger("etl.spark.normalizer")
        self._normalized_count: int = 0
        self._skipped_count: int = 0

    # -------------------------------------------------------------------------
    # Main Normalization
    # -------------------------------------------------------------------------

    def normalize(
        self,
        raw_data: SparkEnrichedMovie,
    ) -> SparkNormalized | None:
        """Normalize a single Spark record.

        Args:
            raw_data: Raw enriched Spark data.

        Returns:
            Normalized data or None if invalid.
        """
        if not self._is_valid(raw_data):
            self._skipped_count += 1
            return None

        normalized = self._build_normalized(raw_data)
        self._normalized_count += 1
        return normalized

    def normalize_batch(
        self,
        raw_records: list[SparkEnrichedMovie],
    ) -> list[SparkNormalized]:
        """Normalize multiple records.

        Args:
            raw_records: List of raw Spark data.

        Returns:
            List of normalized data (invalid records skipped).
        """
        normalized: list[SparkNormalized] = []
        for record in raw_records:
            result = self.normalize(record)
            if result is not None:
                normalized.append(result)

        self._log_batch_result(len(raw_records), len(normalized))
        return normalized

    def _log_batch_result(self, total: int, normalized: int) -> None:
        """Log batch normalization result.

        Args:
            total: Total input records.
            normalized: Successfully normalized count.
        """
        skipped = total - normalized
        self._logger.info(f"Normalized {normalized}/{total} records ({skipped} skipped)")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _is_valid(self, raw_data: SparkEnrichedMovie) -> bool:
        """Check if raw data is valid for normalization.

        Args:
            raw_data: Raw Spark data.

        Returns:
            True if valid.
        """
        has_id = self._has_valid_id(raw_data)
        has_title = self._has_valid_title(raw_data)
        has_rating = self._has_valid_rating(raw_data)

        return has_id and has_title and has_rating

    @staticmethod
    def _has_valid_id(raw_data: SparkEnrichedMovie) -> bool:
        """Check for valid Kaggle ID.

        Args:
            raw_data: Raw Spark data.

        Returns:
            True if ID is valid.
        """
        kaggle_id = raw_data.get("kaggle_id")
        return kaggle_id is not None and kaggle_id > 0

    @staticmethod
    def _has_valid_title(raw_data: SparkEnrichedMovie) -> bool:
        """Check for valid title.

        Args:
            raw_data: Raw Spark data.

        Returns:
            True if title is valid.
        """
        title = raw_data.get("title")
        return bool(title and title.strip())

    @staticmethod
    def _has_valid_rating(raw_data: SparkEnrichedMovie) -> bool:
        """Check for valid rating data.

        Args:
            raw_data: Raw Spark data.

        Returns:
            True if rating data is valid.
        """
        rating = raw_data.get("rating")
        votes = raw_data.get("votes")
        return rating is not None and votes is not None

    # -------------------------------------------------------------------------
    # Building Normalized Data
    # -------------------------------------------------------------------------

    def _build_normalized(
        self,
        raw_data: SparkEnrichedMovie,
    ) -> SparkNormalized:
        """Build normalized data from raw record.

        Args:
            raw_data: Raw Spark data.

        Returns:
            Normalized Spark data.
        """
        return SparkNormalized(
            kaggle_id=raw_data["kaggle_id"],
            title=self._clean_title(raw_data.get("title", "")),
            release_year=self._safe_int_or_none(raw_data.get("release_year")),
            decade=self._safe_int_or_none(raw_data.get("decade")),
            rating=self._safe_float(raw_data.get("rating")),
            votes=self._safe_int(raw_data.get("votes")),
            popularity=self._safe_float(raw_data.get("popularity")),
            runtime=self._safe_runtime(raw_data.get("runtime")),
            overview=self._clean_text(raw_data.get("overview")),
            genre_names=self._clean_text(raw_data.get("genre_names")),
            rating_category=self._get_rating_category(raw_data),
            source=self.SOURCE_NAME,
        )

    # -------------------------------------------------------------------------
    # Type Conversion Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _safe_float(value: float | int | str | None) -> float:
        """Safely convert to float.

        Args:
            value: Value to convert.

        Returns:
            Float value or 0.0.
        """
        if value is None:
            return 0.0
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _safe_int(value: int | float | str | None) -> int:
        """Safely convert to int.

        Args:
            value: Value to convert.

        Returns:
            Int value or 0.
        """
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _safe_int_or_none(value: int | float | str | None) -> int | None:
        """Safely convert to int or None.

        Args:
            value: Value to convert.

        Returns:
            Int value or None.
        """
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_runtime(value: int | float | str | None) -> int | None:
        """Safely convert runtime.

        Args:
            value: Runtime value.

        Returns:
            Runtime in minutes or None if invalid.
        """
        if value is None:
            return None
        try:
            runtime = int(value)
            # Validate reasonable runtime (1 min to 600 min)
            return runtime if 1 <= runtime <= 600 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _clean_title(title: str | None) -> str:
        """Clean and normalize title.

        Args:
            title: Raw title.

        Returns:
            Cleaned title.
        """
        if not title:
            return ""
        return title.strip()

    @staticmethod
    def _clean_text(text: str | None) -> str | None:
        """Clean optional text field.

        Args:
            text: Raw text.

        Returns:
            Cleaned text or None.
        """
        if not text:
            return None
        cleaned = text.strip()
        return cleaned if cleaned else None

    def _get_rating_category(self, raw_data: SparkEnrichedMovie) -> str:
        """Get or compute rating category.

        Args:
            raw_data: Raw Spark data.

        Returns:
            Rating category string.
        """
        # Use pre-computed if available
        category = raw_data.get("rating_category")
        if category:
            return category

        # Compute from rating
        rating = self._safe_float(raw_data.get("rating"))
        return self._compute_rating_category(rating)

    @staticmethod
    def _compute_rating_category(rating: float) -> str:
        """Compute rating category from score.

        Args:
            rating: Rating value.

        Returns:
            Category string.
        """
        if rating >= 7.5:
            category = "excellent"
        elif rating >= 6.0:
            category = "good"
        elif rating >= 4.0:
            category = "average"
        else:
            category = "poor"
        return category

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, int]:
        """Get normalization statistics.

        Returns:
            Dict with normalized and skipped counts.
        """
        return {
            "normalized": self._normalized_count,
            "skipped": self._skipped_count,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._normalized_count = 0
        self._skipped_count = 0
