"""TMDB extraction and loading pipelines.

Orchestrates full TMDB data extraction and insertion into PostgreSQL.
All parameters are read from settings (.env file).
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.database import get_database
from src.etl.extractors.tmdb import TMDBExtractor
from src.etl.loaders.tmdb import TMDBLoader
from src.etl.types import ETLResult
from src.etl.utils import setup_logger
from src.settings import settings

logger = setup_logger("etl.pipelines.tmdb")


@dataclass
class PipelineResult:
    """Result of pipelines execution.

    Attributes:
        extracted: Number of films extracted from TMDB.
        loaded: Number of films successfully loaded to DB.
        errors: Number of loading errors.
        duration_seconds: Total pipelines duration.
        started_at: Pipeline start timestamp.
        finished_at: Pipeline end timestamp.
    """

    extracted: int
    loaded: int
    errors: int
    duration_seconds: float
    started_at: datetime
    finished_at: datetime

    @property
    def success_rate(self) -> float:
        """Calculate loading success rate."""
        total = self.loaded + self.errors
        return (self.loaded / total * 100) if total > 0 else 0.0


class TMDBPipeline:
    """Pipeline for TMDB data extraction and loading.

    Reads all configuration from settings (.env):
    - TMDB_YEAR_MIN / TMDB_YEAR_MAX: Year range
    - TMDB_ENRICH_MOVIES: Whether to fetch details
    - TMDB_MAX_PAGES: Max pages per year
    - Database connection settings
    """

    def __init__(self) -> None:
        """Initialize pipelines components."""
        self._logger = setup_logger("etl.pipelines.tmdb")
        self._db = get_database()
        self._extractor = TMDBExtractor()
        self._loaded_count = 0
        self._error_count = 0

    def run(self) -> PipelineResult:
        """Execute full TMDB extraction and loading pipelines.

        Returns:
            PipelineResult with execution statistics.
        """
        started_at = datetime.now()
        self._log_start()

        with self._db.session() as session:
            loader = TMDBLoader(session)
            etl_result = self._run_extraction(loader, session)
            session.commit()

        finished_at = datetime.now()
        return self._build_result(etl_result, started_at, finished_at)

    def _log_start(self) -> None:
        """Log pipelines start with settings info."""
        self._logger.info("=" * 60)
        self._logger.info("TMDB Pipeline Starting")
        self._logger.info("=" * 60)
        self._logger.info(f"Year range: {settings.tmdb.year_min}-{settings.tmdb.year_max}")
        self._logger.info(f"Enrich movies: {settings.tmdb.enrich_movies}")
        self._logger.info(f"Max pages/year: {settings.tmdb.max_pages}")
        self._logger.info("=" * 60)

    def _run_extraction(
        self,
        loader: TMDBLoader,
        session: Session,
    ) -> ETLResult:
        """Run extraction with callback to loader.

        Args:
            loader: TMDB loader instance.
            session: Database session for flush.

        Returns:
            ETLResult from extractor.
        """
        self._loaded_count = 0
        self._error_count = 0

        def on_batch(bundles: list[dict[str, Any]]) -> None:
            """

            :param bundles:
            :return:
            """
            self._process_batch(bundles, loader, session)

        # Uses settings.tmdb.* by default (no kwargs needed)
        return self._extractor.extract_with_callback(callback=on_batch)

    def _process_batch(
        self,
        bundles: list[dict[str, Any]],
        loader: TMDBLoader,
        session: Session,
    ) -> None:
        """Process a batch of film bundles by loading them into the database.

        This method takes a list of normalized film bundles, loads them using the provided
        TMDB loader, and updates the loading statistics. It's designed to be called
        as a callback during the extraction process.

        Args:
            bundles: List of dictionaries containing normalized film data bundles.
            loader: TMDBLoader instance used to load the data into the database.
            session: SQLAlchemy session for database operations.

        Note:
            This method updates the instance's `_loaded_count` and `_error_count` attributes
            with the results of the batch processing.
        """
        stats = loader.load_bundles(bundles)
        self._loaded_count += stats.inserted
        self._error_count += stats.errors
        session.flush()

    def _build_result(
        self,
        etl_result: ETLResult,
        started_at: datetime,
        finished_at: datetime,
    ) -> PipelineResult:
        """Build final pipelines result.

        Args:
            etl_result: Result from extractor.
            started_at: Start timestamp.
            finished_at: End timestamp.

        Returns:
            Complete PipelineResult.
        """
        duration = (finished_at - started_at).total_seconds()

        result = PipelineResult(
            extracted=etl_result["count"],
            loaded=self._loaded_count,
            errors=self._error_count,
            duration_seconds=duration,
            started_at=started_at,
            finished_at=finished_at,
        )

        self._log_result(result)
        return result

    def _log_result(self, result: PipelineResult) -> None:
        """Log final pipelines results."""
        self._logger.info("=" * 60)
        self._logger.info("TMDB Pipeline Complete")
        self._logger.info("=" * 60)
        self._logger.info(f"Extracted: {result.extracted}")
        self._logger.info(f"Loaded: {result.loaded}")
        self._logger.info(f"Errors: {result.errors}")
        self._logger.info(f"Success rate: {result.success_rate:.1f}%")
        self._logger.info(f"Duration: {result.duration_seconds:.1f}s")
        self._logger.info("=" * 60)


def run_tmdb_pipeline() -> PipelineResult:
    """Convenience function to run TMDB pipelines.

    Returns:
        PipelineResult with execution statistics.
    """
    pipeline = TMDBPipeline()
    return pipeline.run()


def main() -> int:
    """CLI entry point for TMDB pipelines.

    Returns:
        Exit code (0 success, 1 failure).
    """
    try:
        result = run_tmdb_pipeline()
        return 0 if result.errors == 0 else 1
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
