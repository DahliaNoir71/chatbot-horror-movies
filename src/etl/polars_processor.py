"""Polars BigData processor for large-scale data transformations.

Source 6 (E1): BigData processing with Polars (Rust-based DataFrame).
Handles aggregation, deduplication, and normalization across all sources.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, TypedDict

import polars as pl

from src.etl.extractors.base_extractor import BaseExtractor
from src.etl.utils import setup_logger
from src.settings import settings

# File extensions
CSV_EXT: Final[str] = ".csv"
PARQUET_EXT: Final[str] = ".parquet"
JSON_EXT: Final[str] = ".json"


class CsvReadOptions(TypedDict, total=False):
    """Type hints for read_csv options."""

    has_header: bool
    separator: str
    comment_char: str | None
    quote_char: str | None
    skip_rows: int
    dtypes: Mapping[str, pl.DataType | type] | None
    null_values: str | list[str] | dict[str, str] | None
    ignore_errors: bool
    parse_dates: bool
    n_rows: int | None
    skip_rows_after_header: int
    encoding: str
    low_memory: bool
    rechunk: bool
    storage_options: dict[str, Any] | None
    skip_rows_before_header: int
    row_count_name: str | None
    row_count_offset: int
    try_parse_dates: bool
    eol_char: str
    new_columns: Sequence[str] | None
    raise_if_empty: bool
    truncate_ragged_lines: bool


@dataclass
class PolarsStats:
    """Processing statistics."""

    sources_processed: int = 0
    total_input_rows: int = 0
    total_output_rows: int = 0
    duplicates_removed: int = 0
    null_rows_removed: int = 0
    memory_mb: float = 0.0


class PolarsProcessor(BaseExtractor):
    """BigData processor using Polars for high-performance transformations.

    Polars advantages over Pandas:
    - Rust-based, multi-threaded by default
    - Lazy evaluation for query optimization
    - Lower memory footprint
    - Native parallel execution
    """

    def __init__(self) -> None:
        """Initialize Polars processor."""
        super().__init__("PolarsProcessor")
        self.logger = setup_logger("etl.polars")
        self.paths = settings.paths
        self.stats = PolarsStats()

    def validate_config(self) -> None:
        """No external config required for Polars."""
        pass

    # =========================================================================
    # DATA LOADING
    # =========================================================================

    def load_json(self, path: Path) -> pl.DataFrame:
        """Load JSON file into Polars DataFrame.

        Args:
            path: Path to JSON file.

        Returns:
            Polars DataFrame.
        """
        self.logger.info(f"loading_json: {path.name}")
        df = pl.read_json(path)
        self.stats.total_input_rows += len(df)
        return df

    def load_csv(self, path: Path, **kwargs: CsvReadOptions) -> pl.DataFrame:
        """Load CSV file into Polars DataFrame.

        Args:
            path: Path to CSV file.
            **kwargs: Additional read_csv arguments. See CsvReadOptions for available options.

        Returns:
            Polars DataFrame.
        """
        self.logger.info(f"loading_csv: {path.name}")
        df = pl.read_csv(path, **kwargs)
        self.stats.total_input_rows += len(df)
        return df

    def load_parquet(self, path: Path) -> pl.DataFrame:
        """Load Parquet file into Polars DataFrame.

        Args:
            path: Path to Parquet file.

        Returns:
            Polars DataFrame.
        """
        self.logger.info(f"loading_parquet: {path.name}")
        df = pl.read_parquet(path)
        self.stats.total_input_rows += len(df)
        return df

    def from_dicts(self, data: list[dict[str, Any]]) -> pl.DataFrame:
        """Create DataFrame from list of dictionaries.

        Args:
            data: List of row dictionaries.

        Returns:
            Polars DataFrame.
        """
        df = pl.DataFrame(data)
        self.stats.total_input_rows += len(df)
        return df

    # =========================================================================
    # DATA TRANSFORMATIONS
    # =========================================================================

    def deduplicate(
        self,
        df: pl.DataFrame,
        subset: list[str] | None = None,
        keep: str = "first",
    ) -> pl.DataFrame:
        """Remove duplicate rows.

        Args:
            df: Input DataFrame.
            subset: Columns to consider for duplicates.
            keep: Which duplicate to keep ("first", "last", "none").

        Returns:
            Deduplicated DataFrame.
        """
        initial_count = len(df)

        df = df.unique(subset=subset, keep=keep) if subset else df.unique(keep=keep)

        removed = initial_count - len(df)
        self.stats.duplicates_removed += removed

        self.logger.info(f"duplicates_removed: {removed}")
        return df

    def drop_nulls(
        self,
        df: pl.DataFrame,
        subset: list[str] | None = None,
    ) -> pl.DataFrame:
        """Remove rows with null values.

        Args:
            df: Input DataFrame.
            subset: Columns to check for nulls.

        Returns:
            Cleaned DataFrame.
        """
        initial_count = len(df)

        df = df.drop_nulls(subset=subset) if subset else df.drop_nulls()

        removed = initial_count - len(df)
        self.stats.null_rows_removed += removed

        self.logger.info(f"null_rows_removed: {removed}")
        return df

    def normalize_text(self, df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
        """Normalize text columns (strip, lowercase).

        Args:
            df: Input DataFrame.
            columns: Text columns to normalize.

        Returns:
            DataFrame with normalized text.
        """
        for col in columns:
            if col in df.columns:
                df = df.with_columns(pl.col(col).str.strip_chars().str.to_lowercase().alias(col))
        return df

    def cast_types(
        self,
        df: pl.DataFrame,
        schema: dict[str, pl.DataType],
    ) -> pl.DataFrame:
        """Cast columns to specified types.

        Args:
            df: Input DataFrame.
            schema: Column name to type mapping.

        Returns:
            DataFrame with casted types.
        """
        for col, dtype in schema.items():
            if col in df.columns:
                df = df.with_columns(pl.col(col).cast(dtype, strict=False))
        return df

    def add_metadata(self, df: pl.DataFrame, source: str) -> pl.DataFrame:
        """Add extraction metadata columns.

        Args:
            df: Input DataFrame.
            source: Source name.

        Returns:
            DataFrame with metadata.
        """
        return df.with_columns(
            [
                pl.lit(source).alias("source"),
                pl.lit(datetime.now().isoformat()).alias("extracted_at"),
            ]
        )

    # =========================================================================
    # AGGREGATION
    # =========================================================================

    def union_sources(self, dataframes: list[pl.DataFrame]) -> pl.DataFrame:
        """Union multiple DataFrames with schema alignment.

        Args:
            dataframes: List of DataFrames to union.

        Returns:
            Combined DataFrame.
        """
        if not dataframes:
            return pl.DataFrame()

        if len(dataframes) == 1:
            return dataframes[0]

        self.logger.info(f"unioning_sources: {len(dataframes)} DataFrames")

        # Get all unique columns
        all_columns: set[str] = set()
        for df in dataframes:
            all_columns.update(df.columns)

        # Align schemas by adding missing columns as null
        aligned: list[pl.DataFrame] = []
        for df in dataframes:
            missing = all_columns - set(df.columns)
            if missing:
                df = df.with_columns([pl.lit(None).alias(col) for col in missing])
            # Reorder columns consistently
            df = df.select(sorted(all_columns))
            aligned.append(df)

        result = pl.concat(aligned, how="vertical_relaxed")
        self.stats.sources_processed = len(dataframes)

        self.logger.info(f"union_complete: {len(result)} total rows")
        return result

    def aggregate_by_title(self, df: pl.DataFrame) -> pl.DataFrame:
        """Aggregate data by title, merging duplicate entries.

        Args:
            df: Input DataFrame with potential duplicates.

        Returns:
            Aggregated DataFrame.
        """
        self.logger.info("aggregating_by_title")

        # Group by normalized title and year
        return df.group_by(["title", "year"]).agg(
            [
                # Keep first non-null value for each column
                pl.col("imdb_id").drop_nulls().first(),
                pl.col("tmdb_id").drop_nulls().first(),
                pl.col("overview").drop_nulls().first(),
                pl.col("tagline").drop_nulls().first(),
                pl.col("runtime").drop_nulls().first(),
                pl.col("genres").drop_nulls().first(),
                # Average scores
                pl.col("vote_average").mean().alias("vote_average"),
                pl.col("vote_count").sum().alias("vote_count"),
                # Collect all sources
                pl.col("source").unique().alias("sources"),
                # Latest extraction
                pl.col("extracted_at").max().alias("extracted_at"),
            ]
        )

    # =========================================================================
    # LAZY EVALUATION
    # =========================================================================

    def lazy_process(
        self,
        path: Path,
        operations: list[tuple[str, dict[str, Any]]],
    ) -> pl.DataFrame:
        """Process large file using lazy evaluation.

        Args:
            path: Path to data file (CSV, Parquet, JSON).
            operations: List of (operation_name, params) tuples.

        Returns:
            Processed DataFrame.
        """
        self.logger.info(f"lazy_processing: {path.name}")

        # Create lazy frame based on file type
        suffix = path.suffix.lower()
        if suffix == CSV_EXT:
            lf = pl.scan_csv(path)
        elif suffix == PARQUET_EXT:
            lf = pl.scan_parquet(path)
        elif suffix == JSON_EXT:
            lf = pl.scan_ndjson(path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        # Apply operations lazily
        for op_name, params in operations:
            lf = self._apply_lazy_operation(lf, op_name, params)

        # Collect results
        return lf.collect()

    def _apply_lazy_operation(
        self,
        lf: pl.LazyFrame,
        op_name: str,
        params: dict[str, Any],
    ) -> pl.LazyFrame:
        """Apply single operation to lazy frame.

        Args:
            lf: Input LazyFrame.
            op_name: Operation name.
            params: Operation parameters.

        Returns:
            Transformed LazyFrame.
        """

        # Par défaut, on retourne le LazyFrame inchangé
        result = lf

        match op_name:
            case "filter":
                result = lf.filter(params["condition"])
            case "select":
                result = lf.select(params["columns"])
            case "drop_nulls":
                result = lf.drop_nulls(subset=params.get("subset"))
            case "unique":
                result = lf.unique(subset=params.get("subset"))
            case "sort":
                result = lf.sort(params["by"], descending=params.get("descending", False))
            case "limit":
                result = lf.limit(params["n"])
            case _:
                self.logger.warning(f"unknown_operation: {op_name}")

        return result

    # =========================================================================
    # OUTPUT
    # =========================================================================

    def save_parquet(self, df: pl.DataFrame, path: Path) -> Path:
        """Save DataFrame to Parquet file.

        Args:
            df: DataFrame to save.
            path: Output path.

        Returns:
            Path to saved file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path, compression="zstd")

        self.logger.info(f"saved_parquet: {path.name} ({len(df)} rows)")
        return path

    def save_csv(self, df: pl.DataFrame, path: Path) -> Path:
        """Save DataFrame to CSV file.

        Args:
            df: DataFrame to save.
            path: Output path.

        Returns:
            Path to saved file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_csv(path)

        self.logger.info(f"saved_csv: {path.name} ({len(df)} rows)")
        return path

    def save_json(self, df: pl.DataFrame, path: Path) -> Path:
        """Save DataFrame to JSON file.

        Args:
            df: DataFrame to save.
            path: Output path.

        Returns:
            Path to saved file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_json(path)

        self.logger.info(f"saved_json: {path.name} ({len(df)} rows)")
        return path

    def to_dicts(self, df: pl.DataFrame) -> list[dict[str, Any]]:
        """Convert DataFrame to list of dictionaries.

        Args:
            df: Input DataFrame.

        Returns:
            List of row dictionaries.
        """
        return df.to_dicts()

    # =========================================================================
    # MAIN PROCESSING
    # =========================================================================

    def extract(
        self,
        sources: dict[str, list[dict[str, Any]]] | None = None,
        input_path: Path | None = None,
        output_path: Path | None = None,
        **_kwargs: Any,
    ) -> pl.DataFrame:
        """Process and aggregate data from multiple sources.

        Args:
            sources: Dictionary of source_name -> list of records.
            input_path: Alternative: path to input file.
            output_path: Optional path to save results.

        Returns:
            Processed Polars DataFrame.
        """
        self._start_extraction()

        self.logger.info("=" * 60)
        self.logger.info("⚡ POLARS BIGDATA PROCESSING STARTED")
        self.logger.info("=" * 60)

        dataframes: list[pl.DataFrame] = []

        # Load from sources dict
        if sources:
            for source_name, records in sources.items():
                if records:
                    df = self.from_dicts(records)
                    df = self.add_metadata(df, source_name)
                    dataframes.append(df)
                    self.logger.info(f"loaded_source: {source_name} ({len(df)} rows)")

        # Load from file
        if input_path and input_path.exists():
            df = self._load_file(input_path)
            dataframes.append(df)

        # Union all sources
        if not dataframes:
            self.logger.warning("no_data_to_process")
            return pl.DataFrame()

        combined = self.union_sources(dataframes)

        # Apply standard transformations
        combined = self._apply_standard_transforms(combined)

        # Update stats
        self.stats.total_output_rows = len(combined)
        self.stats.memory_mb = combined.estimated_size("mb")

        # Save if output path provided
        if output_path:
            self._save_output(combined, output_path)

        self._end_extraction()
        self._log_stats()

        return combined

    def _load_file(self, path: Path) -> pl.DataFrame:
        """Load file based on extension.

        Args:
            path: File path.

        Returns:
            Loaded DataFrame.
        """
        suffix = path.suffix.lower()
        if suffix == CSV_EXT:
            return self.load_csv(path)
        elif suffix == PARQUET_EXT:
            return self.load_parquet(path)
        elif suffix == JSON_EXT:
            return self.load_json(path)
        else:
            raise ValueError(f"unsupported_file_format: {suffix}")

    # ...

    def _save_output(self, df: pl.DataFrame, path: Path) -> None:
        """Save output based on extension.

        Args:
            df: DataFrame to save.
            path: Output path.
        """
        suffix = path.suffix.lower()
        if suffix == CSV_EXT:
            self.save_csv(df, path)
        elif suffix == PARQUET_EXT:
            self.save_parquet(df, path)
        elif suffix == JSON_EXT:
            self.save_json(df, path)
        else:
            # Default to parquet
            self.save_parquet(df, path.with_suffix(".parquet"))

        # ...
        self.logger.info(f"Sources processed  : {self.stats.sources_processed}")
        self.logger.info(f"Input rows         : {self.stats.total_input_rows}")
        self.logger.info(f"Output rows        : {self.stats.total_output_rows}")
        self.logger.info(f"Duplicates removed : {self.stats.duplicates_removed}")
        self.logger.info(f"Null rows removed  : {self.stats.null_rows_removed}")
        self.logger.info(f"Memory usage       : {self.stats.memory_mb:.2f} MB")
        self.logger.info(f"Duration           : {self.metrics.duration_seconds:.2f}s")
        self.logger.info("=" * 60)
