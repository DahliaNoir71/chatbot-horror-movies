"""Spark Big Data extraction pipeline.

Orchestrates PySpark extraction, SparkSQL analytics, and data export.
Validates C1 (Big Data extraction) and C2 (SparkSQL queries).
All parameters are read from settings (.env file).
"""

import os

from dotenv import load_dotenv

load_dotenv()
_java_home = os.getenv("JAVA_HOME")
if _java_home:
    os.environ["JAVA_HOME"] = _java_home
    os.environ["PATH"] = f"{_java_home}/bin;{os.environ.get('PATH', '')}"

import sys  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime  # noqa: E402

from src.etl.extractors.spark import SparkExtractor  # noqa: E402
from src.etl.types import ETLResult  # noqa: E402
from src.etl.utils import setup_logger  # noqa: E402
from src.settings.sources.spark import SparkSettings  # noqa: E402

logger = setup_logger("etl.pipeline.spark")


@dataclass
class SparkAnalyticsResult:
    """Results from SparkSQL analytical queries (C2 validation).

    Attributes:
        decades_count: Number of decades analyzed.
        languages_count: Number of languages analyzed.
        top_movies_count: Top movies with context.
        genres_count: Genre combinations analyzed.
    """

    decades_count: int = 0
    languages_count: int = 0
    top_movies_count: int = 0
    genres_count: int = 0


@dataclass
class PipelineResult:
    """Result of Spark pipeline execution.

    Attributes:
        total_rows: Total rows in CSV.
        filtered: Movies after filtering.
        normalized: Successfully normalized records.
        exported: Records exported to Parquet.
        errors: Number of errors.
        duration_seconds: Total pipeline duration.
        started_at: Pipeline start timestamp.
        finished_at: Pipeline end timestamp.
        analytics: SparkSQL analytics results.
        export_path: Path to exported data.
    """

    total_rows: int
    filtered: int
    normalized: int
    exported: int
    errors: int
    duration_seconds: float
    started_at: datetime
    finished_at: datetime
    analytics: SparkAnalyticsResult = field(default_factory=SparkAnalyticsResult)
    export_path: str | None = None

    @property
    def success_rate(self) -> float:
        """Calculate normalization success rate."""
        if self.filtered == 0:
            return 0.0
        return self.normalized / self.filtered * 100


class SparkPipeline:
    """Pipeline for Spark Big Data extraction and analytics.

    Reads all configuration from settings (.env):
    - SPARK_CSV_FILENAME: Source CSV file
    - SPARK_MIN_VOTES / SPARK_MIN_RATING: Filters
    - SPARK_EXPORT_FORMAT: Output format
    - SPARK_DRIVER_MEMORY: Spark memory allocation

    Validates:
    - C1: Big Data extraction from CSV via Spark
    - C2: SparkSQL queries (window functions, CTEs, aggregations)
    """

    def __init__(self, settings: SparkSettings | None = None) -> None:
        """Initialize pipeline components.

        Args:
            settings: Spark settings (uses defaults from .env if None).
        """
        self._logger = setup_logger("etl.pipeline.spark")
        self._settings = settings or SparkSettings()
        self._extractor: SparkExtractor | None = None
        self._errors: list[str] = []

    def run(self, export: bool = True, analytics: bool = True) -> PipelineResult:
        """Execute full Spark extraction and analytics pipeline.

        Args:
            export: Whether to export data to Parquet.
            analytics: Whether to run C2 analytical queries.

        Returns:
            PipelineResult with execution statistics.
        """
        started_at = datetime.now()
        self._log_start()
        self._errors = []

        result = self._execute_pipeline(export, analytics)

        finished_at = datetime.now()
        result.started_at = started_at
        result.finished_at = finished_at
        result.duration_seconds = (finished_at - started_at).total_seconds()

        self._log_result(result)
        return result

    def _execute_pipeline(self, export: bool, analytics: bool) -> PipelineResult:
        """Execute pipeline stages.

        Args:
            export: Whether to export data.
            analytics: Whether to run analytics.

        Returns:
            Partial PipelineResult (timestamps added by caller).
        """
        result = PipelineResult(
            total_rows=0,
            filtered=0,
            normalized=0,
            exported=0,
            errors=0,
            duration_seconds=0.0,
            started_at=datetime.now(),
            finished_at=datetime.now(),
        )

        try:
            with SparkExtractor(settings=self._settings) as extractor:
                self._extractor = extractor
                result = self._run_stages(extractor, export, analytics, result)
        except Exception as e:
            self._log_error(f"Pipeline failed: {e}")
            result.errors = len(self._errors)

        return result

    def _run_stages(
        self,
        extractor: SparkExtractor,
        export: bool,
        analytics: bool,
        result: PipelineResult,
    ) -> PipelineResult:
        """Run all pipeline stages.

        Args:
            extractor: Active SparkExtractor.
            export: Whether to export.
            analytics: Whether to run analytics.
            result: Result to populate.

        Returns:
            Updated PipelineResult.
        """
        # Stage 1: Extract and count
        result.total_rows, result.filtered = self._stage_extract(extractor)

        # Stage 2: Run SparkSQL analytics (C2)
        if analytics:
            result.analytics = self._stage_analytics(extractor)

        # Stage 3: Normalize data
        result.normalized = self._stage_normalize(extractor)

        # Stage 4: Export to Parquet
        if export:
            result.exported, result.export_path = self._stage_export(extractor)

        result.errors = len(self._errors)
        return result

    # -------------------------------------------------------------------------
    # Pipeline Stages
    # -------------------------------------------------------------------------

    def _stage_extract(self, extractor: SparkExtractor) -> tuple[int, int]:
        """Stage 1: Extract data from CSV.

        Args:
            extractor: SparkExtractor instance.

        Returns:
            Tuple of (total_rows, filtered_count).
        """
        self._logger.info("[Stage 1/4] Extracting data from CSV...")

        etl_result: ETLResult = extractor.extract()

        if not etl_result["success"]:
            for error in etl_result.get("errors", []):
                self._log_error(error)

        stats = extractor.get_extraction_stats()
        self._logger.info(f"Total rows: {stats['total_rows']}")
        self._logger.info(f"Filtered: {stats['filtered_movies']}")

        return stats["total_rows"], stats["filtered_movies"]

    def _stage_analytics(self, extractor: SparkExtractor) -> SparkAnalyticsResult:
        """Stage 2: Run SparkSQL analytical queries (C2 validation).

        Args:
            extractor: SparkExtractor instance.

        Returns:
            SparkAnalyticsResult with query results.
        """
        self._logger.info("[Stage 2/4] Running SparkSQL analytics (C2)...")

        analytics = SparkAnalyticsResult()

        # Decade statistics (GROUP BY, aggregations)
        decades = extractor.get_stats_by_decade()
        analytics.decades_count = len(decades)
        self._log_analytics("Stats by decade", analytics.decades_count)

        # Language statistics (CASE WHEN, conditional aggregation)
        languages = extractor.get_stats_by_language()
        analytics.languages_count = len(languages)
        self._log_analytics("Stats by language", analytics.languages_count)

        # Top movies with context (CTE, JOINs, window functions)
        top_movies = extractor.get_top_movies_with_context()
        analytics.top_movies_count = len(top_movies)
        self._log_analytics("Top movies with context", analytics.top_movies_count)

        # Genre analysis (Spark string functions)
        genres = extractor.get_genre_analysis()
        analytics.genres_count = len(genres)
        self._log_analytics("Genre combinations", analytics.genres_count)

        return analytics

    def _log_analytics(self, query_name: str, count: int) -> None:
        """Log analytics query result.

        Args:
            query_name: Name of the query.
            count: Number of results.
        """
        self._logger.info(f"  - {query_name}: {count} results")

    def _stage_normalize(self, extractor: SparkExtractor) -> int:
        """Stage 3: Normalize extracted data.

        Args:
            extractor: SparkExtractor instance.

        Returns:
            Number of normalized records.
        """
        self._logger.info("[Stage 3/4] Normalizing data...")

        normalized = extractor.extract_normalized()
        count = len(normalized)

        self._logger.info(f"Normalized: {count} records")
        return count

    def _stage_export(self, extractor: SparkExtractor) -> tuple[int, str | None]:
        """Stage 4: Export data to Parquet.

        Args:
            extractor: SparkExtractor instance.

        Returns:
            Tuple of (exported_count, export_path).
        """
        self._logger.info("[Stage 4/4] Exporting to Parquet...")

        try:
            count = extractor.export_to_parquet()
            export_path = str(self._settings.parquet_output_path)
            self._logger.info(f"Exported: {count} records to {export_path}")
            return count, export_path
        except Exception as e:
            self._log_error(f"Export failed: {e}")
            return 0, None

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    def _log_start(self) -> None:
        """Log pipeline start with settings info."""
        self._logger.info("=" * 60)
        self._logger.info("Spark Pipeline Starting (C1/C2 Validation)")
        self._logger.info("=" * 60)
        self._logger.info(f"CSV: {self._settings.csv_path}")
        self._logger.info(f"Min votes: {self._settings.min_votes}")
        self._logger.info(f"Min rating: {self._settings.min_rating}")
        self._logger.info(f"Driver memory: {self._settings.driver_memory}")
        self._logger.info(f"Export format: {self._settings.export_format}")
        self._logger.info("=" * 60)

    def _log_result(self, result: PipelineResult) -> None:
        """Log final pipeline results."""
        self._logger.info("=" * 60)
        self._logger.info("Spark Pipeline Complete")
        self._logger.info("=" * 60)
        self._logger.info(f"Total rows: {result.total_rows}")
        self._logger.info(f"Filtered: {result.filtered}")
        self._logger.info(f"Normalized: {result.normalized}")
        self._logger.info(f"Exported: {result.exported}")
        self._logger.info(f"Success rate: {result.success_rate:.1f}%")
        self._logger.info(f"Errors: {result.errors}")
        self._logger.info(f"Duration: {result.duration_seconds:.1f}s")
        if result.export_path:
            self._logger.info(f"Export path: {result.export_path}")
        self._logger.info("-" * 60)
        self._logger.info("C2 Analytics Summary:")
        self._logger.info(f"  - Decades analyzed: {result.analytics.decades_count}")
        self._logger.info(f"  - Languages analyzed: {result.analytics.languages_count}")
        self._logger.info(f"  - Top movies: {result.analytics.top_movies_count}")
        self._logger.info(f"  - Genre combinations: {result.analytics.genres_count}")
        self._logger.info("=" * 60)

    def _log_error(self, message: str) -> None:
        """Log and track an error.

        Args:
            message: Error message.
        """
        self._logger.error(message)
        self._errors.append(message)


def run_spark_pipeline(
    export: bool = True,
    analytics: bool = True,
) -> PipelineResult:
    """Convenience function to run Spark pipeline.

    Args:
        export: Whether to export to Parquet.
        analytics: Whether to run C2 analytics.

    Returns:
        PipelineResult with execution statistics.
    """
    pipeline = SparkPipeline()
    return pipeline.run(export=export, analytics=analytics)


def main() -> int:
    """CLI entry point for Spark pipeline.

    Returns:
        Exit code (0 success, 1 failure).
    """
    try:
        result = run_spark_pipeline(export=False)
        return 0 if result.errors == 0 else 1
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
