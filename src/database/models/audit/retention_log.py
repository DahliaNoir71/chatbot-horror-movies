"""DataRetentionLog model for GDPR data retention tracking.

Logs data deletion and anonymization operations.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class DataRetentionLog(Base):
    """Log of data retention operations.

    Tracks deletion and anonymization for GDPR compliance.

    Attributes:
        id: Primary key.
        operation_type: Type of operation (delete, anonymize).
        table_name: Target table name.
        records_affected: Number of records processed.
        criteria: Selection criteria used.
        executed_by: User or process that executed.
        status: Operation status (success, failed, partial).
        error_message: Error details if failed.
    """

    __tablename__ = "data_retention_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Operation details
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    records_affected: Mapped[int] = mapped_column(Integer, default=0)

    # Criteria and context
    criteria: Mapped[str | None] = mapped_column(Text)
    executed_by: Mapped[str] = mapped_column(String(100), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<DataRetentionLog(id={self.id}, "
            f"op='{self.operation_type}', table='{self.table_name}', "
            f"records={self.records_affected})>"
        )
