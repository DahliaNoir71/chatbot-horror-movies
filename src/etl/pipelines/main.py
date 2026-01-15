"""Main ETL orchestrator for E1 validation.

Executes all pipelines sequentially in dependency order.
Stops immediately on any failure - all data is required for RAG.
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.etl.utils import setup_logger

logger = setup_logger("etl.pipelines.main")


class PipelineStatus(Enum):
    """Pipeline execution status."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ABORTED = "aborted"


@dataclass
class PipelineStepResult:
    """Result of a single pipelines step.

    Attributes:
        name: Pipeline name.
        status: Execution status.
        records: Records processed.
        errors: Error count.
        duration_seconds: Execution time.
        message: Status message.
    """

    name: str
    status: PipelineStatus
    records: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    message: str = ""


@dataclass
class OrchestratorResult:
    """Result of full orchestration.

    Attributes:
        steps: Results for each pipelines.
        total_records: Total records across all pipelines.
        total_errors: Total errors across all pipelines.
        duration_seconds: Total execution time.
        started_at: Start timestamp.
        finished_at: End timestamp.
        aborted: Whether orchestration was aborted.
        abort_reason: Reason for abort.
    """

    steps: list[PipelineStepResult] = field(default_factory=list)
    total_records: int = 0
    total_errors: int = 0
    duration_seconds: float = 0.0
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime = field(default_factory=datetime.now)
    aborted: bool = False
    abort_reason: str = ""

    @property
    def success_count(self) -> int:
        """Count successful pipelines."""
        return sum(1 for s in self.steps if s.status == PipelineStatus.SUCCESS)

    @property
    def overall_status(self) -> PipelineStatus:
        """Determine overall orchestration status."""
        if self.aborted:
            return PipelineStatus.ABORTED
        if all(s.status in (PipelineStatus.SUCCESS, PipelineStatus.SKIPPED) for s in self.steps):
            return PipelineStatus.SUCCESS
        return PipelineStatus.FAILED


class ETLOrchestrator:
    """Orchestrates all E1 ETL pipelines.

    Executes pipelines in dependency order:
    1. TMDB (primary source - REST API)
    2. Kaggle (additional films - CSV)
    3. Spark (Big Data analytics - C1/C2)
    4. IMDB (enrichment - SQLite/C2)
    5. Rotten Tomatoes (enrichment - Scraping)

    Stops immediately on any failure.
    """

    def __init__(
        self,
        skip_tmdb: bool = False,
        skip_kaggle: bool = False,
        skip_spark: bool = False,
        skip_imdb: bool = False,
        skip_rt: bool = False,
    ) -> None:
        """Initialize orchestrator.

        Args:
            skip_tmdb: Skip TMDB pipelines.
            skip_kaggle: Skip Kaggle pipelines.
            skip_spark: Skip Spark pipelines.
            skip_imdb: Skip IMDB pipelines.
            skip_rt: Skip Rotten Tomatoes pipelines.
        """
        self._logger = setup_logger("etl.pipelines.main")
        self._skip_tmdb = skip_tmdb
        self._skip_kaggle = skip_kaggle
        self._skip_spark = skip_spark
        self._skip_imdb = skip_imdb
        self._skip_rt = skip_rt
        self._result = OrchestratorResult()

    def run(self) -> OrchestratorResult:
        """Execute all pipelines sequentially. Stop on any failure.

        Returns:
            OrchestratorResult with all step results.
        """
        self._result = OrchestratorResult(started_at=datetime.now())
        self._log_start()

        pipelines = [
            ("TMDB", self._skip_tmdb, self._run_tmdb),
            ("Kaggle", self._skip_kaggle, self._run_kaggle),
            ("Spark", self._skip_spark, self._run_spark),
            ("IMDB", self._skip_imdb, self._run_imdb),
            ("RT", self._skip_rt, self._run_rt),
        ]

        for name, skip, runner in pipelines:
            if skip:
                self._add_skipped(name)
                continue

            success = runner()
            if not success:
                self._abort(f"{name} pipelines failed")
                break

        return self._finalize_and_return()

    # -------------------------------------------------------------------------
    # Pipeline Runners (return bool: True=success, False=failure)
    # -------------------------------------------------------------------------

    def _run_tmdb(self) -> bool:
        """Run TMDB pipelines (Source 1: REST API).

        Returns:
            True if successful, False otherwise.
        """
        self._log_pipeline_start(1, 5, "TMDB", "REST API")

        try:
            from src.etl.pipelines.tmdb import run_tmdb_pipeline

            result = run_tmdb_pipeline()

            if result.errors > 0:
                self._add_failed("TMDB", f"{result.errors} errors during extraction")
                return False

            self._add_success(
                name="TMDB",
                records=result.extracted,
                duration=result.duration_seconds,
            )
            return True

        except Exception as e:
            self._add_failed("TMDB", str(e))
            return False

    def _run_kaggle(self) -> bool:
        """Run Kaggle pipelines (Source 2: CSV File).

        Returns:
            True if successful, False otherwise.
        """
        self._log_pipeline_start(2, 5, "Kaggle", "CSV File")

        try:
            from src.etl.pipelines.kaggle import KagglePipeline

            pipeline = KagglePipeline()
            result = pipeline.run()

            if result.errors > 0:
                self._add_failed("Kaggle", f"{result.errors} errors during extraction")
                return False

            self._add_success(
                name="Kaggle",
                records=result.rows_normalized,
                duration=result.duration_seconds,
            )
            return True

        except Exception as e:
            self._add_failed("Kaggle", str(e))
            return False

    def _run_spark(self) -> bool:
        """Run Spark pipelines (Source 3: Big Data - C1/C2).

        Returns:
            True if successful, False otherwise.
        """
        self._log_pipeline_start(3, 5, "Spark", "Big Data - C1/C2")

        try:
            from src.etl.pipelines.spark import run_spark_pipeline

            result = run_spark_pipeline(export=False, analytics=True)

            if result.errors > 0:
                self._add_failed("Spark", f"{result.errors} errors during extraction")
                return False

            self._add_success(
                name="Spark",
                records=result.normalized,
                duration=result.duration_seconds,
            )
            return True

        except Exception as e:
            self._add_failed("Spark", str(e))
            return False

    def _run_imdb(self) -> bool:
        """Run IMDB pipelines (Source 4: SQLite - C2).

        Returns:
            True if successful, False otherwise.
        """
        self._log_pipeline_start(4, 5, "IMDB", "SQLite - C2")

        try:
            from src.etl.pipelines.imdb import IMDBPipeline

            pipeline = IMDBPipeline()
            result = pipeline.run()

            if result.errors > 0:
                self._add_failed("IMDB", f"{result.errors} errors during extraction")
                return False

            self._add_success(
                name="IMDB",
                records=result.movies_normalized,
                duration=result.duration_seconds,
            )
            return True

        except Exception as e:
            self._add_failed("IMDB", str(e))
            return False

    def _run_rt(self) -> bool:
        """Run Rotten Tomatoes pipelines (Source 5: Web Scraping).

        Returns:
            True if successful, False otherwise.
        """
        self._log_pipeline_start(5, 5, "Rotten Tomatoes", "Web Scraping")

        try:
            from src.etl.pipelines.rotten_tomatoes import RTPipeline

            pipeline = RTPipeline()
            result = pipeline.run(limit=100)

            if result.errors > 0:
                self._add_failed("RT", f"{result.errors} errors during extraction")
                return False

            self._add_success(
                name="RT",
                records=result.scores_loaded,
                duration=result.duration_seconds,
            )
            return True

        except Exception as e:
            self._add_failed("RT", str(e))
            return False

    # -------------------------------------------------------------------------
    # Result Helpers
    # -------------------------------------------------------------------------

    def _add_success(self, name: str, records: int, duration: float) -> None:
        """Add successful pipelines result.

        Args:
            name: Pipeline name.
            records: Records processed.
            duration: Execution time.
        """
        self._result.steps.append(
            PipelineStepResult(
                name=name,
                status=PipelineStatus.SUCCESS,
                records=records,
                errors=0,
                duration_seconds=duration,
                message=f"Processed {records} records",
            )
        )
        self._result.total_records += records
        self._logger.info(f"{name} completed: {records} records in {duration:.1f}s")

    def _add_failed(self, name: str, error: str) -> None:
        """Add failed pipelines result.

        Args:
            name: Pipeline name.
            error: Error message.
        """
        self._logger.error(f"{name} pipelines failed: {error}")
        self._result.steps.append(
            PipelineStepResult(
                name=name,
                status=PipelineStatus.FAILED,
                message=error,
            )
        )
        self._result.total_errors += 1

    def _add_skipped(self, name: str) -> None:
        """Add skipped pipelines result.

        Args:
            name: Pipeline name.
        """
        self._logger.info(f"Skipping {name} pipelines")
        self._result.steps.append(
            PipelineStepResult(
                name=name,
                status=PipelineStatus.SKIPPED,
                message="Skipped by configuration",
            )
        )

    def _abort(self, reason: str) -> None:
        """Abort orchestration.

        Args:
            reason: Abort reason.
        """
        self._logger.error(f"ABORTING: {reason}")
        self._result.aborted = True
        self._result.abort_reason = reason

    def _finalize_and_return(self) -> OrchestratorResult:
        """Finalize and return orchestration result.

        Returns:
            Final OrchestratorResult.
        """
        self._result.finished_at = datetime.now()
        self._result.duration_seconds = (
            self._result.finished_at - self._result.started_at
        ).total_seconds()
        self._log_summary()
        return self._result

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    def _log_start(self) -> None:
        """Log orchestration start."""
        self._logger.info("=" * 60)
        self._logger.info("E1 ETL ORCHESTRATOR")
        self._logger.info("=" * 60)
        self._logger.info("Pipelines to execute:")
        self._logger.info(f"  1. TMDB:   {'SKIP' if self._skip_tmdb else 'RUN'}")
        self._logger.info(f"  2. Kaggle: {'SKIP' if self._skip_kaggle else 'RUN'}")
        self._logger.info(f"  3. Spark:  {'SKIP' if self._skip_spark else 'RUN'}")
        self._logger.info(f"  4. IMDB:   {'SKIP' if self._skip_imdb else 'RUN'}")
        self._logger.info(f"  5. RT:     {'SKIP' if self._skip_rt else 'RUN'}")
        self._logger.info("=" * 60)

    def _log_pipeline_start(
        self,
        step: int,
        total: int,
        name: str,
        source_type: str,
    ) -> None:
        """Log pipelines start.

        Args:
            step: Current step number.
            total: Total steps.
            name: Pipeline name.
            source_type: Type of data source.
        """
        self._logger.info("")
        self._logger.info("=" * 60)
        self._logger.info(f"[{step}/{total}] {name} Pipeline ({source_type})")
        self._logger.info("=" * 60)

    def _log_summary(self) -> None:
        """Log orchestration summary."""
        self._logger.info("")
        self._logger.info("=" * 60)
        self._logger.info("E1 ORCHESTRATION SUMMARY")
        self._logger.info("=" * 60)
        self._logger.info("")

        for step in self._result.steps:
            icon = self._get_status_icon(step.status)
            self._logger.info(
                f"  {icon} {step.name:12} | "
                f"{step.records:>6} records | "
                f"{step.duration_seconds:>6.1f}s | "
                f"{step.message}"
            )

        self._logger.info("")
        self._logger.info("-" * 60)
        self._logger.info(f"  Total Records: {self._result.total_records}")
        self._logger.info(f"  Total Errors:  {self._result.total_errors}")
        self._logger.info(f"  Total Time:    {self._result.duration_seconds:.1f}s")
        self._logger.info(f"  Status:        {self._result.overall_status.value.upper()}")

        if self._result.aborted:
            self._logger.info(f"  Abort Reason:  {self._result.abort_reason}")

        self._logger.info("=" * 60)

    @staticmethod
    def _get_status_icon(status: PipelineStatus) -> str:
        """Get status icon for logging.

        Args:
            status: Pipeline status.

        Returns:
            Status icon string.
        """
        icons = {
            PipelineStatus.SUCCESS: "[OK]",
            PipelineStatus.FAILED: "[XX]",
            PipelineStatus.SKIPPED: "[--]",
            PipelineStatus.ABORTED: "[!!]",
        }
        return icons.get(status, "[??]")


def run_all_pipelines(
    skip_tmdb: bool = False,
    skip_kaggle: bool = False,
    skip_spark: bool = False,
    skip_imdb: bool = False,
    skip_rt: bool = False,
) -> OrchestratorResult:
    """Run all E1 pipelines. Stop on any failure.

    Args:
        skip_tmdb: Skip TMDB pipelines.
        skip_kaggle: Skip Kaggle pipelines.
        skip_spark: Skip Spark pipelines.
        skip_imdb: Skip IMDB pipelines.
        skip_rt: Skip Rotten Tomatoes pipelines.

    Returns:
        OrchestratorResult with all results.
    """
    orchestrator = ETLOrchestrator(
        skip_tmdb=skip_tmdb,
        skip_kaggle=skip_kaggle,
        skip_spark=skip_spark,
        skip_imdb=skip_imdb,
        skip_rt=skip_rt,
    )
    return orchestrator.run()


def main() -> int:
    """CLI entry point for E1 orchestrator.

    Returns:
        Exit code (0 success, 1 failure/aborted).
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="E1 ETL Orchestrator - Run all extraction pipelines"
    )
    parser.add_argument("--skip-tmdb", action="store_true", help="Skip TMDB pipelines")
    parser.add_argument("--skip-kaggle", action="store_true", help="Skip Kaggle pipelines")
    parser.add_argument("--skip-spark", action="store_true", help="Skip Spark pipelines")
    parser.add_argument("--skip-imdb", action="store_true", help="Skip IMDB pipelines")
    parser.add_argument("--skip-rt", action="store_true", help="Skip RT pipelines")
    parser.add_argument(
        "--only",
        type=str,
        choices=["tmdb", "kaggle", "spark", "imdb", "rt"],
        help="Run only specified pipelines",
    )

    args = parser.parse_args()

    # Handle --only flag
    if args.only:
        skip_config = {
            "skip_tmdb": args.only != "tmdb",
            "skip_kaggle": args.only != "kaggle",
            "skip_spark": args.only != "spark",
            "skip_imdb": args.only != "imdb",
            "skip_rt": args.only != "rt",
        }
    else:
        skip_config = {
            "skip_tmdb": args.skip_tmdb,
            "skip_kaggle": args.skip_kaggle,
            "skip_spark": args.skip_spark,
            "skip_imdb": args.skip_imdb,
            "skip_rt": args.skip_rt,
        }

    try:
        result = run_all_pipelines(**skip_config)
        return 0 if result.overall_status == PipelineStatus.SUCCESS else 1

    except Exception as e:
        logger.exception(f"Orchestrator failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
