"""Rotten Tomatoes enrichment pipeline.

Orchestrates RT scraping for films already in database.
Requires TMDB pipeline to have been executed first.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from src.database.connection import get_database
from src.etl.extractors.rotten_tomatoes import RTExtractor
from src.etl.loaders.rotten_tomatoes import RTScoreLoader
from src.etl.types import FilmToEnrich, NormalizedRTScoreData
from src.etl.utils import setup_logger


@dataclass
class RTPipelineResult:
    """Results from RT pipeline execution."""

    films_processed: int = 0
    scores_loaded: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    error_messages: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.films_processed
        if total == 0:
            return 100.0
        return round((1 - self.errors / total) * 100, 2)


class RTPipeline:
    """Orchestrates RT enrichment for existing films.

    This pipeline enriches films already in the database
    with Rotten Tomatoes scores and critics consensus.

    Requires:
        - TMDB pipeline executed (films table populated)
        - Network access to rottentomatoes.com
    """

    def __init__(self, session: Session | None = None) -> None:
        """Initialize RT pipeline.

        Args:
            session: Optional SQLAlchemy session.
        """
        self._session = session
        self._logger = setup_logger("etl.pipeline.rt")
        self._extractor = RTExtractor()
        self._result = RTPipelineResult()

    def run(self, limit: int | None = None, batch_size: int = 10) -> RTPipelineResult:
        """Execute RT enrichment pipeline.

        Args:
            limit: Max films to process (None = all).
            batch_size: Films per batch for DB commits.

        Returns:
            RTPipelineResult with statistics.
        """
        return asyncio.run(self.run_async(limit=limit, batch_size=batch_size))

    async def run_async(
        self,
        limit: int | None = None,
        batch_size: int = 10,
    ) -> RTPipelineResult:
        """Execute RT enrichment pipeline asynchronously.

        Args:
            limit: Max films to process (None = all).
            batch_size: Films per batch for DB commits.

        Returns:
            RTPipelineResult with statistics.
        """
        start_time = datetime.now()
        self._logger.info("=" * 60)
        self._logger.info("Starting Rotten Tomatoes enrichment pipeline")
        self._logger.info("=" * 60)

        try:
            await self._execute_pipeline(limit, batch_size)
        except Exception as e:
            self._logger.error(f"Pipeline failed: {e}")
            self._result.error_messages.append(str(e))

        self._result.duration_seconds = (datetime.now() - start_time).total_seconds()
        self._log_final_results()

        return self._result

    async def _execute_pipeline(self, limit: int | None, batch_size: int) -> None:
        """Execute pipeline steps.

        Args:
            limit: Max films to process.
            batch_size: Batch size for commits.
        """
        session = self._get_session()
        loader = RTScoreLoader(session)

        # Step 1: Get films without RT scores
        films = loader.get_films_without_rt(limit=limit)
        self._result.films_processed = len(films)

        if not films:
            self._logger.info("No films to enrich - all have RT scores")
            return

        self._logger.info(f"Found {len(films)} films to enrich")

        # Step 2: Extract and load in batches
        await self._process_films(films, loader, batch_size)

    async def _process_films(
        self,
        films: list[FilmToEnrich],
        loader: RTScoreLoader,
        batch_size: int,
    ) -> None:
        """Process films in batches.

        Args:
            films: Films to process.
            loader: RT score loader.
            batch_size: Batch size.
        """
        batch: list[NormalizedRTScoreData] = []

        def flush_batch(normalized: list[NormalizedRTScoreData]) -> None:
            """Callback to load batch into DB."""
            nonlocal batch
            if normalized:
                stats = loader.load(normalized)
                self._result.scores_loaded += stats.inserted + stats.updated
                self._result.errors += stats.errors

        await self._extractor.extract_with_callback(
            films=films,
            callback=flush_batch,
            batch_size=batch_size,
        )

    def _get_session(self) -> Session:
        """Get or create database session.

        Returns:
            SQLAlchemy session.
        """
        if self._session is None:
            self._session = get_database().get_sync_session()
        return self._session

    def _log_final_results(self) -> None:
        """Log pipeline results summary."""
        self._logger.info("=" * 60)
        self._logger.info("RT Pipeline Complete")
        self._logger.info("=" * 60)
        self._logger.info(f"Films processed: {self._result.films_processed}")
        self._logger.info(f"Scores loaded: {self._result.scores_loaded}")
        self._logger.info(f"Errors: {self._result.errors}")
        self._logger.info(f"Success rate: {self._result.success_rate}%")
        self._logger.info(f"Duration: {self._result.duration_seconds:.1f}s")


def main() -> None:
    """Entry point for RT pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="RT Enrichment Pipeline")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max films to process",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for DB commits",
    )

    args = parser.parse_args()

    pipeline = RTPipeline()
    result = pipeline.run(limit=args.limit, batch_size=args.batch_size)

    print(f"\nProcessed: {result.films_processed}")
    print(f"Loaded: {result.scores_loaded}")
    print(f"Errors: {result.errors}")
    print(f"Success rate: {result.success_rate}%")
    print(f"Duration: {result.duration_seconds:.1f}s")


if __name__ == "__main__":
    main()
