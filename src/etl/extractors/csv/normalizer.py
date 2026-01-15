"""Kaggle data normalizer.

Transforms raw CSV data into normalized format
for database insertion.
"""

from datetime import date

from src.etl.types.kaggle import KaggleHorrorMovieNormalized, KaggleHorrorMovieRaw
from src.etl.utils.logger import setup_logger


class KaggleNormalizer:
    """Normalizes Kaggle horror movies data.

    Transforms raw CSV rows into KaggleHorrorMovieNormalized
    ready for database upsert.
    """

    def __init__(self) -> None:
        """Initialize normalizer."""
        self._logger = setup_logger("etl.kaggle.normalizer")
        self._normalized_count: int = 0
        self._skipped_count: int = 0

    # -------------------------------------------------------------------------
    # Main Normalization
    # -------------------------------------------------------------------------

    def normalize(
        self,
        raw_data: KaggleHorrorMovieRaw,
    ) -> KaggleHorrorMovieNormalized | None:
        """Normalize a single raw movie record.

        Args:
            raw_data: Raw movie data from CSV.

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
        raw_records: list[KaggleHorrorMovieRaw],
    ) -> list[KaggleHorrorMovieNormalized]:
        """Normalize multiple records.

        Args:
            raw_records: List of raw movie data.

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
    def _is_valid(raw_data: KaggleHorrorMovieRaw) -> bool:
        """Check if raw data is valid for normalization.

        Args:
            raw_data: Raw movie data.

        Returns:
            True if valid.
        """
        # Must have id
        if not raw_data.get("id"):
            return False

        # Must have title
        title = raw_data.get("title")
        return bool(title and str(title).strip())

    # -------------------------------------------------------------------------
    # Building Normalized Data
    # -------------------------------------------------------------------------

    def _build_normalized(
        self,
        raw_data: KaggleHorrorMovieRaw,
    ) -> KaggleHorrorMovieNormalized:
        """Build normalized data from raw record.

        Args:
            raw_data: Raw movie data.

        Returns:
            Normalized movie data.
        """
        return KaggleHorrorMovieNormalized(
            tmdb_id=raw_data["id"],
            title=self._clean_string(raw_data.get("title", "")),
            original_title=self._clean_string(raw_data.get("original_title")),
            original_language=self._clean_language(raw_data.get("original_language")),
            overview=self._clean_text(raw_data.get("overview")),
            tagline=self._clean_string(raw_data.get("tagline")),
            release_date=self._parse_date(raw_data.get("release_date")),
            poster_path=self._clean_string(raw_data.get("poster_path")),
            backdrop_path=self._clean_string(raw_data.get("backdrop_path")),
            popularity=self._safe_float(raw_data.get("popularity"), 0.0),
            vote_average=self._safe_float(raw_data.get("vote_average"), 0.0),
            vote_count=self._safe_int(raw_data.get("vote_count"), 0),
            budget=self._safe_int(raw_data.get("budget"), 0),
            revenue=self._safe_int(raw_data.get("revenue"), 0),
            runtime=self._safe_int_nullable(raw_data.get("runtime")),
            status=raw_data.get("status") or "Released",
            adult=bool(raw_data.get("adult", False)),
            source="kaggle",
        )

    # -------------------------------------------------------------------------
    # Type Conversion Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _safe_int(value: int | float | str | None, default: int) -> int:
        """Safely convert to int with default.

        Args:
            value: Value to convert.
            default: Default if conversion fails.

        Returns:
            Int value.
        """
        if value is None:
            return default
        try:
            result = int(value)
            return result if result >= 0 else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int_nullable(value: int | float | str | None) -> int | None:
        """Safely convert to int, allowing None.

        Args:
            value: Value to convert.

        Returns:
            Int value or None.
        """
        if value is None:
            return None
        try:
            result = int(value)
            return result if result > 0 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(value: int | float | str | None, default: float) -> float:
        """Safely convert to float with default.

        Args:
            value: Value to convert.
            default: Default if conversion fails.

        Returns:
            Float value.
        """
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    # -------------------------------------------------------------------------
    # String Cleaning Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _clean_string(value: str | None) -> str | None:
        """Clean and validate string value.

        Args:
            value: String to clean.

        Returns:
            Cleaned string or None.
        """
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned if cleaned else None

    @staticmethod
    def _clean_text(value: str | None) -> str | None:
        """Clean text field (overview, etc).

        Args:
            value: Text to clean.

        Returns:
            Cleaned text or None.
        """
        if value is None:
            return None
        cleaned = str(value).strip()
        # Skip placeholder text
        if cleaned.lower() in ("no overview", "no description", "n/a"):
            return None
        return cleaned if len(cleaned) > 10 else None

    @staticmethod
    def _clean_language(value: str | None) -> str | None:
        """Clean language code.

        Args:
            value: Language code.

        Returns:
            Lowercase ISO 639-1 code or None.
        """
        if value is None:
            return None
        cleaned = str(value).strip().lower()
        # Validate ISO 639-1 (2 chars)
        return cleaned if len(cleaned) == 2 else None

    # -------------------------------------------------------------------------
    # Date Parsing
    # -------------------------------------------------------------------------

    def _parse_date(self, value: str | None) -> str | None:
        """Parse date string to ISO format.

        Args:
            value: Date string (YYYY-MM-DD expected).

        Returns:
            ISO date string or None.
        """
        cleaned = self._prepare_date_string(value)
        if cleaned is None:
            return None

        result = self._try_parse_iso_date(cleaned) or self._try_parse_year_only(cleaned)
        if result is None:
            self._logger.debug(f"Unparseable date: {value}")
        return result

    @staticmethod
    def _prepare_date_string(value: str | None) -> str | None:
        """Clean and validate date string input.

        Args:
            value: Raw date string.

        Returns:
            Cleaned string or None if empty/invalid.
        """
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned if cleaned else None

    @staticmethod
    def _try_parse_iso_date(value: str) -> str | None:
        """Try parsing ISO date format.

        Args:
            value: Date string.

        Returns:
            ISO date string or None.
        """
        try:
            parsed = date.fromisoformat(value)
            return parsed.isoformat()
        except ValueError:
            return None

    @staticmethod
    def _try_parse_year_only(value: str) -> str | None:
        """Try parsing year-only format.

        Args:
            value: Year string (e.g., "2023").

        Returns:
            ISO date string (Jan 1) or None.
        """
        try:
            year = int(value)
            if 1900 <= year <= 2100:
                return f"{year}-01-01"
        except ValueError:
            pass
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
