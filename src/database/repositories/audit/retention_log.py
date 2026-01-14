"""Data retention log repository for RGPD compliance.

Tracks data deletion and anonymization operations.
"""

from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models.audit import DataRetentionLog
from src.database.repositories.base import BaseRepository


class RetentionDetailsData(TypedDict, total=False):
    """Typed dictionary for retention operation details."""

    criteria: str
    retention_days: int
    dry_run: bool


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
        operation_type: str,
        records_affected: int,
        executed_by: str = "system",
        criteria: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> DataRetentionLog:
        """Log a data retention operation.

        Args:
            table_name: Target table name.
            operation_type: Operation type (delete, anonymize, archive).
            records_affected: Number of records processed.
            executed_by: User or system that ran the operation.
            criteria: Selection criteria used.
            status: Operation status (success, failed, partial).
            error_message: Error details if failed.

        Returns:
            Created log entry.
        """
        log = DataRetentionLog(
            table_name=table_name,
            operation_type=operation_type,
            records_affected=records_affected,
            executed_by=executed_by,
            criteria=criteria,
            status=status,
            error_message=error_message,
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

    def get_by_operation(
        self,
        operation_type: str,
        limit: int = 50,
    ) -> list[DataRetentionLog]:
        """Get retention logs by operation type.

        Args:
            operation_type: Operation type to filter.
            limit: Maximum results.

        Returns:
            List of log entries.
        """
        stmt = (
            select(DataRetentionLog)
            .where(DataRetentionLog.operation_type == operation_type)
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

    def get_failed(self, limit: int = 50) -> list[DataRetentionLog]:
        """Get failed retention operations.

        Args:
            limit: Maximum results.

        Returns:
            List of failed log entries.
        """
        stmt = (
            select(DataRetentionLog)
            .where(DataRetentionLog.status == "failed")
            .order_by(DataRetentionLog.executed_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_total_records_affected(self, table_name: str | None = None) -> int:
        """Get total records affected by retention operations.

        Args:
            table_name: Optional table filter.

        Returns:
            Total records affected.
        """
        from sqlalchemy import func

        stmt = select(func.sum(DataRetentionLog.records_affected))
        if table_name:
            stmt = stmt.where(DataRetentionLog.table_name == table_name)

        result = self._session.scalar(stmt)
        return result or 0
