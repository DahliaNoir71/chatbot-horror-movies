"""Big Data extractor using Polars (Spark alternative) - C1/C2 compliance."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None  # type: ignore

from src.etl.extractors.base_extractor import BaseExtractor
from src.etl.utils import setup_logger
from src.settings import settings

# Default file pattern for data files
DEFAULT_FILE_PATTERN = "*.csv"


@dataclass
class BigDataExtractionStats:
    """Statistics for Big Data extraction."""

    total_rows: int = 0
    filtered_rows: int = 0
    partitions_processed: int = 0
    memory_peak_mb: float = 0.0


class SparkExtractor(BaseExtractor):
    """
    Big Data extractor using Polars (lightweight Spark alternative).

    Implements C1/C2 requirements:
    - C1: Extraction from big data system
    - C2: SQL-like queries on large datasets

    Uses Polars LazyFrame for memory-efficient processing.
    Supports Parquet, CSV, and JSON formats at scale.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """
        Initialize Big Data extractor.

        Args:
            data_dir: Directory containing data files
        """
        super().__init__("SparkExtractor")
        self.logger = setup_logger("etl.spark")
        self.data_dir = data_dir or settings.paths.raw_dir
        self.stats = BigDataExtractionStats()

        if not POLARS_AVAILABLE:
            self.logger.warning("Polars not installed. Install with: pip install polars")

    def validate_config(self) -> None:
        """Validate Polars availability."""
        if not POLARS_AVAILABLE:
            raise ImportError(
                "Polars is required for Big Data processing. Install with: pip install polars"
            )

    def extract(self, **kwargs: Any) -> list[dict[str, Any]]:
        """
        Extract and process data using Polars.

        Args:
            **kwargs: Optional parameters
                - file_pattern: Glob pattern for files (default: "*.csv")
                - filter_horror: Filter horror movies only
                - limit: Maximum rows to return
                - columns: Columns to select

        Returns:
            List of processed movie dictionaries
        """
        self._start_extraction()

        file_pattern = kwargs.get("file_pattern", DEFAULT_FILE_PATTERN)
        filter_horror = kwargs.get("filter_horror", True)
        limit = kwargs.get("limit")
        columns = kwargs.get("columns")

        self.logger.info("⚡ Big Data extraction with Polars")
        self.logger.info(f"Data directory: {self.data_dir}")

        movies = self._process_files(file_pattern, filter_horror, limit, columns)

        self._end_extraction()
        self._log_stats()

        return movies

    def _process_files(
        self,
        file_pattern: str,
        filter_horror: bool,
        limit: int | None,
        columns: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Process multiple files using Polars LazyFrame."""
        if not POLARS_AVAILABLE:
            return []

        files = list(self.data_dir.glob(file_pattern))
        if not files:
            self.logger.warning(f"No {DEFAULT_FILE_PATTERN} files found in {self.data_dir}")
            return []

        self.logger.info(f"Processing {len(files)} files")

        all_movies: list[dict[str, Any]] = []

        for file_path in files:
            self.stats.partitions_processed += 1
            movies = self._process_single_file(file_path, filter_horror, columns)
            all_movies.extend(movies)

            if limit and len(all_movies) >= limit:
                all_movies = all_movies[:limit]
                break

        self.stats.filtered_rows = len(all_movies)
        return all_movies

    def _process_single_file(
        self,
        file_path: Path,
        filter_horror: bool,
        columns: list[str] | None,
    ) -> list[dict[str, Any]]:
        """
        Process a single file with Polars.

        Uses LazyFrame for memory efficiency.
        """
        self.logger.info(f"Processing: {file_path.name}")

        try:
            # Use LazyFrame for memory efficiency
            lf = self._read_lazy_frame(file_path)

            if lf is None:
                return []

            # Count total rows
            total = lf.select(pl.count()).collect().item()
            self.stats.total_rows += total

            # Apply filters
            if filter_horror:
                lf = self._apply_horror_filter(lf)

            # Select columns
            if columns:
                available = set(lf.columns)
                valid_cols = [c for c in columns if c in available]
                if valid_cols:
                    lf = lf.select(valid_cols)

            # Collect results
            df = lf.collect()

            # Convert to dictionaries
            return self._dataframe_to_dicts(df)

        except Exception as e:
            self.logger.error(f"❌ Failed to process {file_path}: {e}")
            return []

    def _read_lazy_frame(self, file_path: Path) -> Any | None:
        """Read file into Polars LazyFrame based on extension.

        Args:
            file_path: Path to the file to read

        Returns:
            Polars LazyFrame if successful, None otherwise
        """
        suffix = file_path.suffix.lower()
        result = None

        try:
            if suffix == ".csv":
                result = pl.scan_csv(file_path, ignore_errors=True)
            elif suffix == ".parquet":
                result = pl.scan_parquet(file_path)
            elif suffix == ".json":
                # JSON needs eager loading first
                result = pl.read_json(file_path).lazy()
            else:
                self.logger.warning(f"Unsupported format: {suffix}")
        except Exception as e:
            self.logger.error(f"Failed to read {file_path}: {e}")

        return result

    def _apply_horror_filter(self, lf: "pl.LazyFrame") -> "pl.LazyFrame":
        """Apply horror genre filter using SQL-like expression.

        Args:
            lf: Polars LazyFrame to filter.

        Returns:
            Filtered LazyFrame.
        """
        columns = lf.columns

        genre_col = None
        for col in ["genres", "genre_names", "genre"]:
            if col in columns:
                genre_col = col
                break

        if not genre_col:
            self.logger.warning("No genre column found, skipping filter")
            return lf

        return lf.filter(pl.col(genre_col).str.to_lowercase().str.contains("horror"))

    def _dataframe_to_dicts(self, df: "pl.DataFrame") -> list[dict[str, Any]]:
        """Convert Polars DataFrame to list of dictionaries."""
        records = df.to_dicts()

        # Add source tag
        for record in records:
            record["source"] = "spark_bigdata"

        return records

    def execute_sql_query(
        self,
        query: str,
        file_path: Path | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute SQL query on data (C2 requirement).

        Args:
            query: SQL query string
            file_path: Data file to query (default: first CSV in data_dir)

        Returns:
            Query results as list of dictionaries
        """
        if not POLARS_AVAILABLE:
            raise ImportError("Polars required for SQL queries")

        if not file_path:
            csv_files = list(self.data_dir.glob(DEFAULT_FILE_PATTERN))
            if not csv_files:
                raise FileNotFoundError(f"No {DEFAULT_FILE_PATTERN} files found")
            file_path = csv_files[0]

        self.logger.info(f"Executing SQL: {query[:50]}...")

        # Register DataFrame as table
        df = pl.read_csv(file_path, ignore_errors=True)

        # Execute SQL using Polars SQL context
        ctx = pl.SQLContext(register_globals=True)
        ctx.register("movies", df)

        result = ctx.execute(query)
        return result.to_dicts()

    def aggregate_statistics(
        self,
        file_path: Path | None = None,
    ) -> dict[str, Any]:
        """
        Compute aggregate statistics on dataset.

        Args:
            file_path: Data file to analyze

        Returns:
            Dictionary with aggregate statistics
        """
        if not POLARS_AVAILABLE:
            return {}

        if not file_path:
            csv_files = list(self.data_dir.glob(DEFAULT_FILE_PATTERN))
            if not csv_files:
                self.logger.warning(f"No {DEFAULT_FILE_PATTERN} files found in {self.data_dir}")
                return {}
            file_path = csv_files[0]

        df = pl.read_csv(file_path, ignore_errors=True)

        stats: dict[str, Any] = {
            "total_rows": len(df),
            "columns": df.columns,
        }

        # Numeric aggregations
        if "vote_average" in df.columns:
            stats["avg_rating"] = df["vote_average"].mean()
            stats["max_rating"] = df["vote_average"].max()

        if "popularity" in df.columns:
            stats["avg_popularity"] = df["popularity"].mean()

        if "year" in df.columns or "release_year" in df.columns:
            year_col = "year" if "year" in df.columns else "release_year"
            stats["year_range"] = (df[year_col].min(), df[year_col].max())

        return stats

    def _log_stats(self) -> None:
        """Log extraction statistics."""
        self.logger.info("=" * 60)
        self.logger.info("📊 BIG DATA EXTRACTION STATISTICS")
        self.logger.info("-" * 60)
        self.logger.info(f"Total rows scanned : {self.stats.total_rows:,}")
        self.logger.info(f"Filtered rows      : {self.stats.filtered_rows:,}")
        self.logger.info(f"Partitions         : {self.stats.partitions_processed}")
        self.logger.info(f"Duration           : {self.metrics.duration_seconds:.2f}s")
        self.logger.info("=" * 60)
