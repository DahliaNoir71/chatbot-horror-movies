"""Kaggle CSV pipeline.

Orchestrates extraction, normalization, and loading
of horror movies from Kaggle dataset.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.database.connection import get_database
from src.etl.extractors.csv import CSVExtractor, KaggleNormalizer
from src.etl.loaders.base import LoaderStats
from src.etl.loaders.csv import KaggleLoader
from src.etl.types.kaggle import KaggleHorrorMovieRaw
from src.etl.utils.logger import setup_logger


@dataclass
class KagglePipelineResult:
    """Results from Kaggle pipeline execution.

    Attributes:
        rows_extracted: Total CSV rows read.
        rows_normalized: Valid rows after normalization.
        films_inserted: New films added.
        films_enriched: Existing films updated.
        errors: Error count.
        duration_seconds: Total execution time.
        error_messages: List of error descriptions.
    """

    rows_extracted: int = 0
    rows_normalized: int = 0
    films_inserted: int = 0
    films_enriched: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    error_messages: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.rows_normalized
        if total == 0:
            return 100.0
        return round((1 - self.errors / total) * 100, 2)


class KagglePipeline:
    """Orchestrates Kaggle CSV ETL pipeline.

    Extracts horror movies from Kaggle dataset,
    normalizes data, and loads into PostgreSQL.

    Attributes:
        csv_path: Path to CSV file.
    """

    def __init__(
        self,
        csv_path: Path | None = None,
        session: Session | None = None,
    ) -> None:
        """Initialize Kaggle pipeline.

        Args:
            csv_path: Optional path to CSV file.
            session: Optional SQLAlchemy session.
        """
        self._csv_path = csv_path
        self._session = session
        self._logger = setup_logger("etl.pipeline.kaggle")
        self._result = KagglePipelineResult()

    # -------------------------------------------------------------------------
    # Main Execution
    # -------------------------------------------------------------------------

    def run(self, batch_size: int = 1000) -> KagglePipelineResult:
        """Execute Kaggle ETL pipeline.

        Args:
            batch_size: Records per batch for processing.

        Returns:
            KagglePipelineResult with statistics.
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
        """Execute pipeline steps.

        Args:
            batch_size: Records per batch.
        """
        csv_path = self._resolve_csv_path()
        if csv_path is None:
            raise ValueError("CSV path not configured")

        session = self._get_session()
        extractor = CSVExtractor()
        normalizer = KaggleNormalizer()
        loader = KaggleLoader(session)

        self._process_batches(csv_path, extractor, normalizer, loader, batch_size)

    def _process_batches(
        self,
        csv_path: Path,
        extractor: CSVExtractor,
        normalizer: KaggleNormalizer,
        loader: KaggleLoader,
        batch_size: int,
    ) -> None:
        """Process CSV in batches.

        Args:
            csv_path: Path to CSV file.
            extractor: CSV extractor instance.
            normalizer: Data normalizer instance.
            loader: Database loader instance.
            batch_size: Records per batch.
        """
        for batch_num, raw_batch in enumerate(
            extractor.extract_batches(csv_path, batch_size), start=1
        ):
            self._process_single_batch(raw_batch, normalizer, loader, batch_num)

        self._collect_enrichment_stats(loader)

    def _process_single_batch(
        self,
        raw_batch: list[KaggleHorrorMovieRaw],
        normalizer: KaggleNormalizer,
        loader: KaggleLoader,
        batch_num: int,
    ) -> None:
        """Process a single batch of records.

        Args:
            raw_batch: Raw CSV records.
            normalizer: Data normalizer.
            loader: Database loader.
            batch_num: Current batch number.
        """
        self._result.rows_extracted += len(raw_batch)

        normalized = normalizer.normalize_batch(raw_batch)
        self._result.rows_normalized += len(normalized)

        if normalized:
            stats = loader.load(normalized)
            self._update_result_from_stats(stats)

        self._logger.info(f"Batch {batch_num}: {len(normalized)} normalized")

    def _update_result_from_stats(self, stats: LoaderStats) -> None:
        """Update result from loader stats.

        Args:
            stats: LoaderStats from loader.
        """
        self._result.films_inserted += stats.inserted
        self._result.errors += stats.errors
        self._result.error_messages.extend(stats.error_messages)

    def _collect_enrichment_stats(self, loader: KaggleLoader) -> None:
        """Collect enrichment statistics from loader.

        Args:
            loader: KaggleLoader instance.
        """
        enrichment = loader.get_enrichment_stats()
        self._result.films_enriched = enrichment["films_enriched"]

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def _resolve_csv_path(self) -> Path | None:
        """Resolve CSV path from config or settings.

        Returns:
            Path to CSV file or None.
        """
        if self._csv_path:
            return self._csv_path

        try:
            from src.settings.sources.kaggle import KaggleSettings

            return KaggleSettings().csv_path
        except ImportError:
            self._logger.error("KaggleSettings not available")
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
        """Log pipeline start."""
        self._logger.info("=" * 60)
        self._logger.info("Starting Kaggle CSV pipeline")
        self._logger.info("=" * 60)

    def _log_final_results(self) -> None:
        """Log pipeline results summary."""
        self._logger.info("=" * 60)
        self._logger.info("Kaggle Pipeline Complete")
        self._logger.info("=" * 60)
        self._logger.info(f"Rows extracted: {self._result.rows_extracted}")
        self._logger.info(f"Rows normalized: {self._result.rows_normalized}")
        self._logger.info(f"Films inserted: {self._result.films_inserted}")
        self._logger.info(f"Films enriched: {self._result.films_enriched}")
        self._logger.info(f"Errors: {self._result.errors}")
        self._logger.info(f"Success rate: {self._result.success_rate}%")
        self._logger.info(f"Duration: {self._result.duration_seconds:.1f}s")

    def _handle_pipeline_error(self, error: Exception) -> None:
        """Handle pipeline-level error.

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
    """Entry point for Kaggle pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Kaggle CSV Pipeline")
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to CSV file",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for processing",
    )

    args = parser.parse_args()

    csv_path = Path(args.csv) if args.csv else None
    pipeline = KagglePipeline(csv_path=csv_path)
    result = pipeline.run(batch_size=args.batch_size)

    _print_results(result)


def _print_results(result: KagglePipelineResult) -> None:
    """Print pipeline results to stdout.

    Args:
        result: Pipeline execution result.
    """
    print(f"\nExtracted: {result.rows_extracted}")
    print(f"Normalized: {result.rows_normalized}")
    print(f"Inserted: {result.films_inserted}")
    print(f"Enriched: {result.films_enriched}")
    print(f"Errors: {result.errors}")
    print(f"Success rate: {result.success_rate}%")
    print(f"Duration: {result.duration_seconds:.1f}s")


if __name__ == "__main__":
    main()
