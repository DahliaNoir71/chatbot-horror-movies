"""IMDB SQLite pipelines.

Orchestrates extraction from IMDB SQLite database,
normalization, and enrichment of existing films.

Validates C2 competency with native SQL queries.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.database.connection import get_database
from src.etl.extractors.sqlite import IMDBNormalizer, SQLiteExtractor
from src.etl.loaders.base import LoaderStats
from src.etl.loaders.sqlite import IMDBLoader
from src.etl.types.imdb import IMDBHorrorMovieJoined
from src.etl.utils.logger import setup_logger


@dataclass
class IMDBPipelineResult:
    """Results from IMDB pipelines execution.

    Attributes:
        movies_extracted: Horror movies found in IMDB.
        movies_normalized: Valid records after normalization.
        films_matched: Films matched by imdb_id.
        runtime_updated: Films with runtime enriched.
        not_found: IMDB records without matching film.
        errors: Error count.
        duration_seconds: Total execution time.
        error_messages: List of error descriptions.
    """

    movies_extracted: int = 0
    movies_normalized: int = 0
    films_matched: int = 0
    runtime_updated: int = 0
    not_found: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    error_messages: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.movies_normalized
        if total == 0:
            return 100.0
        return round((1 - self.errors / total) * 100, 2)


class IMDBPipeline:
    """Orchestrates IMDB SQLite ETL pipelines.

    Extracts horror movies from IMDB database using
    native SQL queries (C2 validation), normalizes data,
    and enriches existing films.

    Attributes:
        db_path: Path to IMDB SQLite database.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        session: Session | None = None,
        min_votes: int = 1000,
    ) -> None:
        """Initialize IMDB pipelines.

        Args:
            db_path: Optional path to IMDB SQLite database.
            session: Optional SQLAlchemy session.
            min_votes: Minimum votes filter for quality.
        """
        self._db_path = db_path
        self._session = session
        self._min_votes = min_votes
        self._logger = setup_logger("etl.pipelines.imdb")
        self._result = IMDBPipelineResult()

    # -------------------------------------------------------------------------
    # Main Execution
    # -------------------------------------------------------------------------

    def run(self, batch_size: int = 1000) -> IMDBPipelineResult:
        """Execute IMDB ETL pipelines.

        Args:
            batch_size: Records per batch for processing.

        Returns:
            IMDBPipelineResult with statistics.
        """
        start_time = datetime.now()
        self._log_start()

        try:
            self._execute_pipeline(batch_size)
        except Exception as e:
            self._handle_pipeline_error(e)

        self._result.duration_seconds = self._calculate_duration(start_time)
        self._log_final_results()

        return self._result

    def _execute_pipeline(self, batch_size: int) -> None:
        """Execute pipelines steps.

        Args:
            batch_size: Records per batch.
        """
        db_path = self._resolve_db_path()
        if db_path is None or not db_path.exists():
            raise FileNotFoundError(f"IMDB database not found: {db_path}")

        extractor = SQLiteExtractor(
            db_path=db_path,
            min_votes=self._min_votes,
        )
        normalizer = IMDBNormalizer()
        session = self._get_session()
        loader = IMDBLoader(session)

        self._process_batches(extractor, normalizer, loader, batch_size)

    def _process_batches(
        self,
        extractor: SQLiteExtractor,
        normalizer: IMDBNormalizer,
        loader: IMDBLoader,
        batch_size: int,
    ) -> None:
        """Process IMDB data in batches.

        Args:
            extractor: SQLite extractor instance.
            normalizer: Data normalizer instance.
            loader: Database loader instance.
            batch_size: Records per batch.
        """
        for batch_num, raw_batch in enumerate(extractor.extract_batches(batch_size), start=1):
            self._process_single_batch(raw_batch, normalizer, loader, batch_num)

        self._collect_enrichment_stats(loader)

    def _process_single_batch(
        self,
        raw_batch: list[IMDBHorrorMovieJoined],
        normalizer: IMDBNormalizer,
        loader: IMDBLoader,
        batch_num: int,
    ) -> None:
        """Process a single batch of records.

        Args:
            raw_batch: Raw IMDB records.
            normalizer: Data normalizer.
            loader: Database loader.
            batch_num: Current batch number.
        """
        self._result.movies_extracted += len(raw_batch)

        normalized = normalizer.normalize_batch(raw_batch)
        self._result.movies_normalized += len(normalized)

        if normalized:
            stats = loader.load(normalized)
            self._update_result_from_stats(stats)

        self._logger.info(f"Batch {batch_num}: {len(normalized)} normalized")

    def _update_result_from_stats(self, stats: LoaderStats) -> None:
        """Update result from loader stats.

        Args:
            stats: LoaderStats from loader.
        """
        self._result.films_matched += stats.updated
        self._result.errors += stats.errors
        self._result.error_messages.extend(stats.error_messages)

    def _collect_enrichment_stats(self, loader: IMDBLoader) -> None:
        """Collect enrichment statistics from loader.

        Args:
            loader: IMDBLoader instance.
        """
        enrichment = loader.get_enrichment_stats()
        self._result.runtime_updated = enrichment["runtime_updated"]
        self._result.not_found = enrichment["not_found"]

    # -------------------------------------------------------------------------
    # C2 Validation: SQL Query Demonstrations
    # -------------------------------------------------------------------------

    def demo_sql_queries(self) -> dict[str, object]:
        """Demonstrate SQL queries for C2 validation.

        Executes various SQL queries to showcase
        SQL competency requirements.

        Returns:
            Dictionary with query results.
        """
        db_path = self._resolve_db_path()
        if db_path is None or not db_path.exists():
            return {"error": f"Database not found: {db_path}"}

        extractor = SQLiteExtractor(db_path=db_path, min_votes=self._min_votes)

        results: dict[str, object] = {}

        # Aggregate statistics (AVG, COUNT, MIN, MAX)
        self._logger.info("Executing: horror_statistics")
        results["statistics"] = extractor.get_horror_stats()

        # Top rated with ORDER BY and LIMIT
        self._logger.info("Executing: top_rated_horror")
        top_rated = extractor.get_top_rated_horror(limit=10)
        results["top_10_rated"] = [m["title"] for m in top_rated]

        # Decade filtering with BETWEEN
        self._logger.info("Executing: horror_by_decade (1980s)")
        eighties = extractor.get_horror_by_decade(1980)
        results["1980s_count"] = len(eighties)

        return results

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def _resolve_db_path(self) -> Path | None:
        """Resolve database path from config or settings.

        Returns:
            Path to SQLite database or None.
        """
        if self._db_path:
            return self._db_path

        try:
            from src.settings.sources.imdb import IMDBSettings

            return IMDBSettings().sqlite_path
        except ImportError:
            self._logger.error("IMDBSettings not available")
            return None

    def _get_session(self) -> Session:
        """Get or create database session.

        Returns:
            SQLAlchemy session.
        """
        if self._session is None:
            self._session = get_database().get_sync_session()
        return self._session

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    def _log_start(self) -> None:
        """Log pipelines start."""
        self._logger.info("=" * 60)
        self._logger.info("Starting IMDB SQLite pipelines")
        self._logger.info(f"Min votes filter: {self._min_votes}")
        self._logger.info("=" * 60)

    def _log_final_results(self) -> None:
        """Log pipelines results summary."""
        self._logger.info("=" * 60)
        self._logger.info("IMDB Pipeline Complete")
        self._logger.info("=" * 60)
        self._logger.info(f"Movies extracted: {self._result.movies_extracted}")
        self._logger.info(f"Movies normalized: {self._result.movies_normalized}")
        self._logger.info(f"Films matched: {self._result.films_matched}")
        self._logger.info(f"Runtime updated: {self._result.runtime_updated}")
        self._logger.info(f"Not found: {self._result.not_found}")
        self._logger.info(f"Errors: {self._result.errors}")
        self._logger.info(f"Success rate: {self._result.success_rate}%")
        self._logger.info(f"Duration: {self._result.duration_seconds:.1f}s")

    def _handle_pipeline_error(self, error: Exception) -> None:
        """Handle pipelines-level error.

        Args:
            error: Exception that occurred.
        """
        self._logger.error(f"Pipeline failed: {error}")
        self._result.error_messages.append(str(error))
        self._result.errors += 1

    @staticmethod
    def _calculate_duration(start_time: datetime) -> float:
        """Calculate duration since start.

        Args:
            start_time: Pipeline start time.

        Returns:
            Duration in seconds.
        """
        return (datetime.now() - start_time).total_seconds()


# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------


def main() -> None:
    """Entry point for IMDB pipelines."""
    import argparse

    parser = argparse.ArgumentParser(description="IMDB SQLite Pipeline")
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to IMDB SQLite database",
    )
    parser.add_argument(
        "--min-votes",
        type=int,
        default=1000,
        help="Minimum votes filter (default: 1000)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for processing",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run SQL query demonstrations (C2 validation)",
    )

    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None
    pipeline = IMDBPipeline(db_path=db_path, min_votes=args.min_votes)

    if args.demo:
        _run_demo(pipeline)
    else:
        _run_pipeline(pipeline, args.batch_size)


def _run_demo(pipeline: IMDBPipeline) -> None:
    """Run SQL demonstration.

    Args:
        pipeline: IMDBPipeline instance.
    """
    print("\n=== C2 SQL Query Demonstrations ===\n")
    results = pipeline.demo_sql_queries()

    if "error" in results:
        print(f"Error: {results['error']}")
        return

    print("Statistics (AVG, COUNT, MIN, MAX):")
    for key, value in results.get("statistics", {}).items():
        print(f"  {key}: {value}")

    print("\nTop 10 Rated Horror Movies (ORDER BY, LIMIT):")
    for title in results.get("top_10_rated", []):
        print(f"  - {title}")

    print(f"\n1980s Horror Movies (BETWEEN): {results.get('1980s_count', 0)}")


def _run_pipeline(pipeline: IMDBPipeline, batch_size: int) -> None:
    """Run full pipelines.

    Args:
        pipeline: IMDBPipeline instance.
        batch_size: Batch size.
    """
    result = pipeline.run(batch_size=batch_size)
    _print_results(result)


def _print_results(result: IMDBPipelineResult) -> None:
    """Print pipelines results to stdout.

    Args:
        result: Pipeline execution result.
    """
    print(f"\nExtracted: {result.movies_extracted}")
    print(f"Normalized: {result.movies_normalized}")
    print(f"Matched: {result.films_matched}")
    print(f"Runtime updated: {result.runtime_updated}")
    print(f"Not found: {result.not_found}")
    print(f"Errors: {result.errors}")
    print(f"Success rate: {result.success_rate}%")
    print(f"Duration: {result.duration_seconds:.1f}s")


if __name__ == "__main__":
    main()
