"""CSV extractor for Kaggle horror movies dataset.

Reads and validates horror_movies.csv using Polars
for efficient streaming and memory management.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import polars as pl

from src.etl.extractors.base import BaseExtractor
from src.etl.types import ETLResult
from src.etl.types.kaggle import KaggleExtractionResult, KaggleHorrorMovieRaw


class CSVExtractor(BaseExtractor):
    """Extracts horror movies from Kaggle CSV dataset.

    Uses Polars for efficient reading and filtering.
    Dataset: evangower/horror-movies (TidyTuesday).

    Attributes:
        name: Extractor identifier.
    """

    name = "kaggle_csv"

    # -------------------------------------------------------------------------
    # Column Configuration
    # -------------------------------------------------------------------------

    REQUIRED_COLUMNS: frozenset[str] = frozenset({"id", "title"})

    COLUMN_DTYPES: dict[str, pl.DataType] = {
        "id": pl.Int64,
        "title": pl.Utf8,
        "original_title": pl.Utf8,
        "original_language": pl.Utf8,
        "overview": pl.Utf8,
        "tagline": pl.Utf8,
        "release_date": pl.Utf8,
        "poster_path": pl.Utf8,
        "backdrop_path": pl.Utf8,
        "popularity": pl.Float64,
        "vote_average": pl.Float64,
        "vote_count": pl.Int64,
        "budget": pl.Int64,
        "revenue": pl.Int64,
        "runtime": pl.Int64,
        "status": pl.Utf8,
        "adult": pl.Boolean,
        "genre_names": pl.Utf8,
        "collection_name": pl.Utf8,
    }

    def __init__(self) -> None:
        """Initialize CSV extractor."""
        super().__init__()
        self._valid_rows: int = 0
        self._skipped_rows: int = 0

    # -------------------------------------------------------------------------
    # Main Extraction
    # -------------------------------------------------------------------------

    def extract(self, **kwargs: Any) -> ETLResult:
        """Execute CSV extraction.

        Kwargs:
            csv_path: Path to CSV file (required).
            batch_size: Rows per batch for processing.

        Returns:
            ETLResult with extraction statistics.
        """
        csv_path = self._resolve_csv_path(kwargs)
        if csv_path is None:
            return self._create_error_result("CSV path not provided")

        if not csv_path.exists():
            return self._create_error_result(f"CSV file not found: {csv_path}")

        return self._execute_extraction(csv_path)

    def _resolve_csv_path(self, kwargs: dict[str, Any]) -> Path | None:
        """Resolve CSV path from kwargs or settings.

        Args:
            kwargs: Extraction parameters.

        Returns:
            Path to CSV file or None.
        """
        if "csv_path" in kwargs:
            return Path(kwargs["csv_path"])

        # Fallback to settings
        try:
            from src.settings.sources.kaggle import KaggleSettings

            settings = KaggleSettings()
            return settings.csv_path
        except ImportError:
            return None

    def _execute_extraction(self, csv_path: Path) -> ETLResult:
        """Execute the extraction process.

        Args:
            csv_path: Path to CSV file.

        Returns:
            ETLResult with statistics.
        """
        self._start_extraction()
        self._logger.info(f"Reading CSV: {csv_path}")

        try:
            df = self._read_csv(csv_path)
            df = self._validate_and_filter(df)
            self._extracted_count = len(df)
            self._logger.info(f"Extracted {self._extracted_count} valid rows")
        except Exception as e:
            self._log_error(f"Extraction failed: {e}")

        return self._end_extraction()

    # -------------------------------------------------------------------------
    # CSV Reading
    # -------------------------------------------------------------------------

    def _read_csv(self, csv_path: Path) -> pl.DataFrame:
        """Read CSV file with Polars.

        Args:
            csv_path: Path to CSV file.

        Returns:
            Polars DataFrame.
        """
        return pl.read_csv(
            csv_path,
            schema_overrides=self.COLUMN_DTYPES,
            ignore_errors=True,
            null_values=["", "NA", "N/A", "null", "None"],
        )

    def _validate_and_filter(self, df: pl.DataFrame) -> pl.DataFrame:
        """Validate and filter DataFrame rows.

        Args:
            df: Raw DataFrame.

        Returns:
            Filtered DataFrame with valid rows only.
        """
        initial_count = len(df)

        # Filter: must have id and title
        df = df.filter(pl.col("id").is_not_null() & pl.col("title").is_not_null())

        # Filter: id must be positive
        df = df.filter(pl.col("id") > 0)

        self._skipped_rows = initial_count - len(df)
        self._valid_rows = len(df)

        self._logger.info(f"Filtered: {self._valid_rows} valid, {self._skipped_rows} skipped")
        return df

    # -------------------------------------------------------------------------
    # Data Access Methods
    # -------------------------------------------------------------------------

    def extract_to_dicts(
        self,
        csv_path: Path | None = None,
    ) -> list[KaggleHorrorMovieRaw]:
        """Extract CSV data as list of dictionaries.

        Args:
            csv_path: Optional path to CSV file.

        Returns:
            List of raw movie data dictionaries.
        """
        path = csv_path or self._get_default_path()
        if path is None or not path.exists():
            self._log_error(f"CSV not found: {path}")
            return []

        df = self._read_csv(path)
        df = self._validate_and_filter(df)

        return df.to_dicts()  # type: ignore[return-value]

    def extract_batches(
        self,
        csv_path: Path | None = None,
        batch_size: int = 1000,
    ) -> Iterator[list[KaggleHorrorMovieRaw]]:
        """Yield batches of movie data for memory efficiency.

        Args:
            csv_path: Optional path to CSV file.
            batch_size: Number of rows per batch.

        Yields:
            List of movie dictionaries per batch.
        """
        path = csv_path or self._get_default_path()
        if path is None or not path.exists():
            self._log_error(f"CSV not found: {path}")
            return

        df = self._read_csv(path)
        df = self._validate_and_filter(df)

        for i in range(0, len(df), batch_size):
            batch_df = df.slice(i, batch_size)
            yield batch_df.to_dicts()

    def _get_default_path(self) -> Path | None:
        """Get default CSV path from settings.

        Returns:
            Path or None if not configured.
        """
        try:
            from src.settings.sources.kaggle import KaggleSettings

            return KaggleSettings().csv_path
        except ImportError:
            return None

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_extraction_stats(self) -> KaggleExtractionResult:
        """Get detailed extraction statistics.

        Returns:
            KaggleExtractionResult with counts.
        """
        return KaggleExtractionResult(
            total_rows=self._valid_rows + self._skipped_rows,
            valid_rows=self._valid_rows,
            skipped_rows=self._skipped_rows,
            error_count=len(self._errors),
            duration_seconds=self._calculate_duration(),
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _create_error_result(self, message: str) -> ETLResult:
        """Create an error ETLResult.

        Args:
            message: Error message.

        Returns:
            ETLResult with error status.
        """
        self._log_error(message)
        return ETLResult(
            source=self.name,
            success=False,
            count=0,
            errors=[message],
            duration_seconds=0.0,
        )
