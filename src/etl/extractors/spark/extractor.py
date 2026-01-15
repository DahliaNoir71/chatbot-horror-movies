"""Spark extractor for Big Data processing.

Extracts and transforms horror movie data using PySpark
to validate C1 (Big Data extraction) and C2 (SparkSQL queries).
"""

from collections.abc import Iterator
from pathlib import Path

from src.etl.extractors.base import BaseExtractor
from src.etl.extractors.spark.normalizer import SparkNormalizer
from src.etl.extractors.spark.queries import SparkQueries
from src.etl.types import ETLResult
from src.etl.types.spark import SparkExtractionResult, SparkNormalized
from src.settings.sources.spark import SparkSettings


class SparkExtractor(BaseExtractor):
    """Extracts horror movies using PySpark.

    Processes CSV data with SparkSQL for C1/C2 validation.
    Runs in local mode - no cluster required.

    Attributes:
        name: Extractor identifier.
    """

    name = "spark_kaggle"

    def __init__(
        self,
        settings: SparkSettings | None = None,
        csv_path: Path | None = None,
    ) -> None:
        """Initialize Spark extractor.

        Args:
            settings: Spark configuration settings.
            csv_path: Override CSV path (uses settings if None).
        """
        super().__init__()
        self._settings = settings or SparkSettings()
        self._csv_path = csv_path or self._settings.csv_path
        self._normalizer = SparkNormalizer()
        self._spark: object | None = None
        self._df: object | None = None
        self._total_rows: int = 0

    # -------------------------------------------------------------------------
    # Main Extraction
    # -------------------------------------------------------------------------

    def extract(self, **kwargs: object) -> ETLResult:
        """Execute Spark extraction.

        Kwargs:
            min_votes: Override minimum votes filter.
            min_rating: Override minimum rating filter.

        Returns:
            ETLResult with extraction statistics.
        """
        self._apply_kwargs(kwargs)

        if not self._validate_csv_path():
            return self._create_error_result(f"CSV not found: {self._csv_path}")

        return self._execute_extraction()

    def _apply_kwargs(self, kwargs: dict[str, object]) -> None:
        """Apply kwargs overrides to settings.

        Args:
            kwargs: Extraction parameters.
        """
        if "min_votes" in kwargs:
            self._settings.min_votes = int(kwargs["min_votes"])  # type: ignore[arg-type]
        if "min_rating" in kwargs:
            self._settings.min_rating = float(kwargs["min_rating"])  # type: ignore[arg-type]

    def _validate_csv_path(self) -> bool:
        """Validate CSV path exists.

        Returns:
            True if CSV exists.
        """
        return self._csv_path is not None and self._csv_path.exists()

    def _execute_extraction(self) -> ETLResult:
        """Execute the extraction process.

        Returns:
            ETLResult with statistics.
        """
        self._start_extraction()
        self._logger.info(f"Loading CSV with Spark: {self._csv_path}")

        try:
            self._init_spark()
            self._load_csv()
            self._register_view()
            self._extracted_count = self._count_filtered_movies()
        except Exception as e:
            self._log_error(f"Spark extraction failed: {e}")
        finally:
            self._stop_spark()

        return self._end_extraction()

    def _count_filtered_movies(self) -> int:
        """Count movies matching filters.

        Returns:
            Number of filtered movies.
        """
        query = SparkQueries.horror_movies_filtered(
            min_votes=self._settings.min_votes,
            min_rating=self._settings.min_rating,
        )
        result_df = self._execute_query(query)
        count = result_df.count()  # type: ignore[attr-defined]
        self._logger.info(f"Filtered movies: {count}")
        return count

    # -------------------------------------------------------------------------
    # SparkSQL Query Methods (C2 Validation)
    # -------------------------------------------------------------------------

    def get_ranked_by_year(self, limit: int = 100) -> list[dict[str, object]]:
        """Get movies ranked within each year.

        Demonstrates ROW_NUMBER() window function.

        Args:
            limit: Maximum results.

        Returns:
            List of ranked movies.
        """
        self._ensure_session()
        query = SparkQueries.ranked_by_year()
        return self._execute_and_collect(query, limit)

    def get_rating_percentiles(self, limit: int = 100) -> list[dict[str, object]]:
        """Get movies with rating percentiles.

        Demonstrates PERCENT_RANK() and NTILE().

        Args:
            limit: Maximum results.

        Returns:
            List of movies with percentiles.
        """
        self._ensure_session()
        query = SparkQueries.rating_percentiles()
        return self._execute_and_collect(query, limit)

    def get_stats_by_decade(self) -> list[dict[str, object]]:
        """Get aggregate statistics by decade.

        Demonstrates GROUP BY with aggregations.

        Returns:
            List of decade statistics.
        """
        self._ensure_session()
        query = SparkQueries.stats_by_decade()
        return self._execute_and_collect(query)

    def get_stats_by_language(self) -> list[dict[str, object]]:
        """Get aggregate statistics by language.

        Demonstrates conditional aggregation.

        Returns:
            List of language statistics.
        """
        self._ensure_session()
        query = SparkQueries.stats_by_language()
        return self._execute_and_collect(query)

    def get_top_movies_with_context(self) -> list[dict[str, object]]:
        """Get top movies with decade context.

        Demonstrates CTE (WITH clause).

        Returns:
            List of top movies with context.
        """
        self._ensure_session()
        query = SparkQueries.top_movies_with_context()
        return self._execute_and_collect(query)

    def get_genre_analysis(self) -> list[dict[str, object]]:
        """Analyze genre combinations.

        Demonstrates Spark string functions.

        Returns:
            List of genre statistics.
        """
        self._ensure_session()
        query = SparkQueries.genre_analysis()
        return self._execute_and_collect(query)

    def get_monthly_release_pattern(self) -> list[dict[str, object]]:
        """Analyze release patterns by month.

        Demonstrates temporal functions.

        Returns:
            List of monthly statistics.
        """
        self._ensure_session()
        query = SparkQueries.monthly_release_pattern()
        return self._execute_and_collect(query)

    # -------------------------------------------------------------------------
    # Export Methods
    # -------------------------------------------------------------------------

    def extract_to_list(self) -> list[dict[str, object]]:
        """Extract all filtered movies as list.

        Returns:
            List of movie dictionaries.
        """
        self._ensure_session()
        query = SparkQueries.export_enriched_data(
            min_votes=self._settings.min_votes,
        )
        return self._execute_and_collect(query)

    def extract_normalized(self) -> list[SparkNormalized]:
        """Extract and normalize all filtered movies.

        Returns:
            List of normalized movie data.
        """
        raw_data = self.extract_to_list()
        return self._normalizer.normalize_batch(raw_data)  # type: ignore[arg-type]

    def extract_batches(
        self,
        batch_size: int | None = None,
    ) -> Iterator[list[dict[str, object]]]:
        """Yield batches of movies.

        Args:
            batch_size: Number of rows per batch (uses settings default).

        Yields:
            List of movie dictionaries per batch.
        """
        batch_size = batch_size or self._settings.batch_size
        self._ensure_session()

        query = SparkQueries.export_enriched_data(
            min_votes=self._settings.min_votes,
        )
        result_df = self._execute_query(query)

        all_rows = result_df.collect()  # type: ignore[attr-defined]
        columns = result_df.columns  # type: ignore[attr-defined]

        yield from self._yield_batches(all_rows, columns, batch_size)

    def extract_normalized_batches(
        self,
        batch_size: int | None = None,
    ) -> Iterator[list[SparkNormalized]]:
        """Yield normalized batches of movies.

        Args:
            batch_size: Number of rows per batch.

        Yields:
            List of normalized movie data per batch.
        """
        for batch in self.extract_batches(batch_size):
            yield self._normalizer.normalize_batch(batch)  # type: ignore[arg-type]

    def _yield_batches(
        self,
        rows: list[object],
        columns: list[str],
        batch_size: int,
    ) -> Iterator[list[dict[str, object]]]:
        """Yield rows in batches.

        Args:
            rows: All collected rows.
            columns: Column names.
            batch_size: Rows per batch.

        Yields:
            Batch of dictionaries.
        """
        batch: list[dict[str, object]] = []
        for row in rows:
            batch.append(self._row_to_dict(row, columns))
            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    def export_to_parquet(self, output_path: Path | None = None) -> int:
        """Export enriched data to Parquet format.

        Args:
            output_path: Output directory (uses settings default).

        Returns:
            Number of exported records.
        """
        output_path = output_path or self._settings.parquet_output_path
        output_path.mkdir(parents=True, exist_ok=True)

        self._ensure_session()
        query = SparkQueries.export_enriched_data(
            min_votes=self._settings.min_votes,
        )
        result_df = self._execute_query(query)

        count = result_df.count()  # type: ignore[attr-defined]
        result_df.write.mode("overwrite").parquet(str(output_path))  # type: ignore[attr-defined]

        self._logger.info(f"Exported {count} records to {output_path}")
        return count

    # -------------------------------------------------------------------------
    # Spark Session Management
    # -------------------------------------------------------------------------

    def _init_spark(self) -> None:
        """Initialize Spark session from settings."""
        import os

        from pyspark.sql import SparkSession

        # Use Java 17 if configured (required for PySpark 3.5.x)
        if self._settings.java_home:
            os.environ["JAVA_HOME"] = self._settings.java_home

        builder = SparkSession.builder
        for key, value in self._settings.spark_config.items():
            builder = builder.config(key, value)

        self._spark = builder.getOrCreate()
        self._spark.sparkContext.setLogLevel(  # type: ignore[attr-defined]
            self._settings.log_level,
        )
        self._logger.info("Spark session initialized (local mode)")

    def _stop_spark(self) -> None:
        """Stop Spark session."""
        if self._spark is not None:
            self._spark.stop()  # type: ignore[attr-defined]
            self._spark = None
            self._df = None
            self._logger.debug("Spark session stopped")

    def _ensure_session(self) -> None:
        """Ensure Spark session is active with data loaded."""
        if self._spark is None:
            self._init_spark()
            self._load_csv()
            self._register_view()

    def _load_csv(self) -> None:
        """Load CSV into DataFrame."""
        if self._spark is None:
            raise RuntimeError("Spark session not initialized")

        self._df = (
            self._spark.read.option("header", "true")  # type: ignore[attr-defined]
            .option("inferSchema", "true")
            .option("multiLine", "true")
            .option("escape", '"')
            .csv(str(self._csv_path))
        )

        self._total_rows = self._df.count()  # type: ignore[attr-defined]
        self._logger.info(f"Loaded {self._total_rows} rows from CSV")

    def _register_view(self) -> None:
        """Register DataFrame as SQL view."""
        if self._df is None:
            raise RuntimeError("DataFrame not loaded")

        self._df.createOrReplaceTempView(SparkQueries.VIEW_NAME)  # type: ignore[attr-defined]
        self._logger.debug(f"Registered view: {SparkQueries.VIEW_NAME}")

    # -------------------------------------------------------------------------
    # Query Execution
    # -------------------------------------------------------------------------

    def _execute_query(self, query: str) -> object:
        """Execute SparkSQL query.

        Args:
            query: SparkSQL query string.

        Returns:
            Result DataFrame.
        """
        if self._spark is None:
            raise RuntimeError("Spark session not initialized")

        self._logger.debug(f"Executing query: {query[:100]}...")
        return self._spark.sql(query)  # type: ignore[attr-defined]

    def _execute_and_collect(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        """Execute query and collect results.

        Args:
            query: SparkSQL query string.
            limit: Optional result limit.

        Returns:
            List of result dictionaries.
        """
        result_df = self._execute_query(query)

        if limit is not None:
            result_df = result_df.limit(limit)  # type: ignore[attr-defined]

        rows = result_df.collect()  # type: ignore[attr-defined]
        columns = result_df.columns  # type: ignore[attr-defined]

        return [self._row_to_dict(row, columns) for row in rows]

    @staticmethod
    def _row_to_dict(row: object, columns: list[str]) -> dict[str, object]:
        """Convert Spark Row to dictionary.

        Args:
            row: Spark Row object.
            columns: Column names (kept for interface consistency).

        Returns:
            Dictionary with column names as keys.
        """
        _ = columns
        return row.asDict()  # type: ignore[attr-defined]

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _create_error_result(self, message: str) -> ETLResult:
        """Create error ETLResult.

        Args:
            message: Error message.

        Returns:
            ETLResult with error.
        """
        self._log_error(message)
        return ETLResult(
            source=self.name,
            success=False,
            count=0,
            errors=[message],
            duration_seconds=0.0,
        )

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_extraction_stats(self) -> SparkExtractionResult:
        """Get detailed extraction statistics.

        Returns:
            SparkExtractionResult with counts.
        """
        normalizer_stats = self._normalizer.get_stats()
        return SparkExtractionResult(
            total_rows=self._total_rows,
            filtered_movies=self._extracted_count,
            exported_count=normalizer_stats["normalized"],
            duration_seconds=self._calculate_duration(),
            export_path=str(self._settings.parquet_output_path),
        )

    # -------------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------------

    def __enter__(self) -> "SparkExtractor":
        """Enter context manager."""
        self._init_spark()
        self._load_csv()
        self._register_view()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: object,
    ) -> None:
        """Exit context manager."""
        self._stop_spark()
