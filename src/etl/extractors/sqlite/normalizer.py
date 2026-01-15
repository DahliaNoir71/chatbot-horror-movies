"""IMDB data normalizer.

Transforms raw IMDB SQLite data into normalized format
for database enrichment.
"""

from src.etl.types.imdb import IMDBHorrorMovieJoined, IMDBNormalized
from src.etl.utils.logger import setup_logger


class IMDBNormalizer:
    """Normalizes IMDB extracted data.

    Transforms IMDBHorrorMovieJoined into IMDBNormalized
    ready for film enrichment.
    """

    def __init__(self) -> None:
        """Initialize normalizer."""
        self._logger = setup_logger("etl.imdb.normalizer")
        self._normalized_count: int = 0
        self._skipped_count: int = 0

    # -------------------------------------------------------------------------
    # Main Normalization
    # -------------------------------------------------------------------------

    def normalize(
        self,
        raw_data: IMDBHorrorMovieJoined,
    ) -> IMDBNormalized | None:
        """Normalize a single IMDB record.

        Args:
            raw_data: Raw joined IMDB data.

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
        raw_records: list[IMDBHorrorMovieJoined],
    ) -> list[IMDBNormalized]:
        """Normalize multiple records.

        Args:
            raw_records: List of raw IMDB data.

        Returns:
            List of normalized data (invalid records skipped).
        """
        normalized = []
        for record in raw_records:
            result = self.normalize(record)
            if result:
                normalized.append(result)
        return normalized

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def _is_valid(raw_data: IMDBHorrorMovieJoined) -> bool:
        """Check if raw data is valid for normalization.

        Args:
            raw_data: Raw IMDB data.

        Returns:
            True if valid.
        """
        imdb_id = raw_data.get("imdb_id")
        has_valid_id = imdb_id and IMDBNormalizer._is_valid_imdb_id(imdb_id)
        has_rating_data = raw_data.get("rating") is not None and raw_data.get("votes") is not None

        return bool(has_valid_id and has_rating_data)

    @staticmethod
    def _is_valid_imdb_id(imdb_id: str) -> bool:
        """Validate IMDB ID format.

        Args:
            imdb_id: IMDB tconst.

        Returns:
            True if valid format (tt followed by digits).
        """
        if not imdb_id.startswith("tt"):
            return False
        return imdb_id[2:].isdigit()

    # -------------------------------------------------------------------------
    # Building Normalized Data
    # -------------------------------------------------------------------------

    def _build_normalized(
        self,
        raw_data: IMDBHorrorMovieJoined,
    ) -> IMDBNormalized:
        """Build normalized data from raw record.

        Args:
            raw_data: Raw IMDB data.

        Returns:
            Normalized IMDB data.
        """
        return IMDBNormalized(
            imdb_id=raw_data["imdb_id"],
            imdb_rating=self._safe_float(raw_data.get("rating")),
            imdb_votes=self._safe_int(raw_data.get("votes")),
            runtime=self._safe_runtime(raw_data.get("runtime")),
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
            return round(float(value), 1)
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
    def _safe_runtime(value: int | float | str | None) -> int | None:
        """Safely convert runtime.

        Args:
            value: Runtime value.

        Returns:
            Runtime in minutes or None.
        """
        if value is None:
            return None
        try:
            runtime = int(value)
            # Validate reasonable runtime (1 min to 600 min)
            return runtime if 1 <= runtime <= 600 else None
        except (ValueError, TypeError):
            return None

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
