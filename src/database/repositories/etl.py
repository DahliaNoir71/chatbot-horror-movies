"""ETL run repository for pipeline tracking.

Provides CRUD and query operations for ETL pipeline
execution tracking and audit logging.
"""

from datetime import datetime
from typing import TypedDict
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.database.models.audit import DataRetentionLog, ETLRun
from src.database.repositories.base import BaseRepository


class ETLErrorData(TypedDict, total=False):
    """Typed dictionary for ETL error details."""

    source: str
    message: str
    traceback: str | None
    timestamp: str


class ETLStatsData(TypedDict):
    """Typed dictionary for ETL statistics."""

    total_runs: int
    successful: int
    failed: int
    total_films_processed: int


class RetentionDetailsData(TypedDict, total=False):
    """Typed dictionary for retention operation details."""

    criteria: str
    retention_days: int
    dry_run: bool


class ETLRunRepository(BaseRepository[ETLRun]):
    """Repository for ETLRun entity operations.

    Tracks ETL pipeline executions with per-source
    statistics and error logging.
    """

    model = ETLRun

    def __init__(self, session: Session) -> None:
        """Initialize ETL run repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_run_id(self, run_id: UUID) -> ETLRun | None:
        """Retrieve ETL run by UUID.

        Args:
            run_id: Unique run identifier.

        Returns:
            ETLRun instance or None.
        """
        return self.get_by_field("run_id", run_id)

    def get_latest(self) -> ETLRun | None:
        """Get most recent ETL run.

        Returns:
            Most recent ETLRun or None.
        """
        stmt = select(ETLRun).order_by(ETLRun.started_at.desc()).limit(1)
        return self._session.scalars(stmt).first()

    def get_running(self) -> list[ETLRun]:
        """Get currently running ETL jobs.

        Returns:
            List of running ETL runs.
        """
        return self.get_many_by_field("status", "running")

    def get_recent(self, limit: int = 10) -> list[ETLRun]:
        """Get recent ETL runs.

        Args:
            limit: Maximum results.

        Returns:
            List of recent runs ordered by start time.
        """
        stmt = select(ETLRun).order_by(ETLRun.started_at.desc()).limit(limit)
        return list(self._session.scalars(stmt).all())

    def get_by_status(self, status: str, limit: int = 50) -> list[ETLRun]:
        """Get ETL runs by status.

        Args:
            status: Run status (running, completed, failed, partial).
            limit: Maximum results.

        Returns:
            List of runs with that status.
        """
        stmt = (
            select(ETLRun)
            .where(ETLRun.status == status)
            .order_by(ETLRun.started_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def start_run(self) -> ETLRun:
        """Create a new ETL run in 'running' status.

        Returns:
            Newly created ETLRun.
        """
        run = ETLRun(status="running")
        return self.create(run)

    def complete_run(
        self,
        run_id: int,
        tmdb_count: int = 0,
        rt_count: int = 0,
        youtube_count: int = 0,
        spark_count: int = 0,
        errors: ETLErrorData | None = None,
    ) -> None:
        """Mark ETL run as completed with statistics.

        Args:
            run_id: ETL run primary key.
            tmdb_count: Films extracted from TMDB.
            rt_count: Films scraped from RT.
            youtube_count: Videos extracted from YouTube.
            spark_count: Films enriched via Spark.
            errors: Optional error details.
        """
        total = tmdb_count + rt_count + youtube_count + spark_count
        status = "completed" if not errors else "partial"

        stmt = (
            update(ETLRun)
            .where(ETLRun.id == run_id)
            .values(
                status=status,
                completed_at=datetime.now(),
                tmdb_count=tmdb_count,
                rt_count=rt_count,
                youtube_count=youtube_count,
                spark_count=spark_count,
                total_films=total,
                errors=errors,
            )
        )
        self._session.execute(stmt)
        self._session.flush()

    def fail_run(self, run_id: int, errors: ETLErrorData) -> None:
        """Mark ETL run as failed.

        Args:
            run_id: ETL run primary key.
            errors: Error details.
        """
        stmt = (
            update(ETLRun)
            .where(ETLRun.id == run_id)
            .values(
                status="failed",
                completed_at=datetime.now(),
                errors=errors,
            )
        )
        self._session.execute(stmt)
        self._session.flush()

    def update_counts(
        self,
        run_id: int,
        tmdb_count: int | None = None,
        rt_count: int | None = None,
        youtube_count: int | None = None,
        spark_count: int | None = None,
    ) -> None:
        """Update extraction counts during run.

        Args:
            run_id: ETL run primary key.
            tmdb_count: Optional TMDB count update.
            rt_count: Optional RT count update.
            youtube_count: Optional YouTube count update.
            spark_count: Optional Spark count update.
        """
        values = {}
        if tmdb_count is not None:
            values["tmdb_count"] = tmdb_count
        if rt_count is not None:
            values["rt_count"] = rt_count
        if youtube_count is not None:
            values["youtube_count"] = youtube_count
        if spark_count is not None:
            values["spark_count"] = spark_count

        if values:
            stmt = update(ETLRun).where(ETLRun.id == run_id).values(**values)
            self._session.execute(stmt)
            self._session.flush()

    def get_stats(self) -> ETLStatsData:
        """Get ETL run statistics.

        Returns:
            Dictionary with various stats.
        """
        total_runs = self.count()
        successful = self._session.scalar(
            select(func.count(ETLRun.id)).where(ETLRun.status == "completed")
        )
        failed = self._session.scalar(
            select(func.count(ETLRun.id)).where(ETLRun.status == "failed")
        )
        total_films = self._session.scalar(select(func.sum(ETLRun.total_films)))

        return {
            "total_runs": total_runs,
            "successful": successful or 0,
            "failed": failed or 0,
            "total_films_processed": total_films or 0,
        }


class DataRetentionLogRepository(BaseRepository[DataRetentionLog]):
    """Repository for DataRetentionLog entity operations.

    Tracks data retention operations for RGPD compliance.
    """

    model = DataRetentionLog

    def __init__(self, session: Session) -> None:
        """Initialize data retention log repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def log_operation(
        self,
        table_name: str,
        operation: str,
        records_affected: int,
        executed_by: str = "system",
        details: RetentionDetailsData | None = None,
    ) -> DataRetentionLog:
        """Log a data retention operation.

        Args:
            table_name: Target table name.
            operation: Operation type (purge, anonymize, archive).
            records_affected: Number of records processed.
            executed_by: User or system that ran the operation.
            details: Optional additional details.

        Returns:
            Created log entry.
        """
        log = DataRetentionLog(
            table_name=table_name,
            operation=operation,
            records_affected=records_affected,
            executed_by=executed_by,
            details=details,
        )
        return self.create(log)

    def get_by_table(self, table_name: str, limit: int = 50) -> list[DataRetentionLog]:
        """Get retention logs for a specific table.

        Args:
            table_name: Table name to filter.
            limit: Maximum results.

        Returns:
            List of log entries.
        """
        stmt = (
            select(DataRetentionLog)
            .where(DataRetentionLog.table_name == table_name)
            .order_by(DataRetentionLog.executed_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_recent(self, limit: int = 50) -> list[DataRetentionLog]:
        """Get recent retention logs.

        Args:
            limit: Maximum results.

        Returns:
            List of recent log entries.
        """
        stmt = select(DataRetentionLog).order_by(DataRetentionLog.executed_at.desc()).limit(limit)
        return list(self._session.scalars(stmt).all())
