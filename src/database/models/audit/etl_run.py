"""ETLRun model for pipeline execution tracking.

Logs ETL pipeline runs with metrics and status.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class ETLRun(Base):
    """ETL pipeline execution record.

    Tracks pipeline runs for monitoring and debugging.

    Attributes:
        id: Primary key.
        pipeline_name: Name of the pipeline executed.
        source_name: Data source processed.
        status: Execution status (running, success, failed).
        records_extracted: Number of records extracted.
        records_loaded: Number of records loaded.
        records_failed: Number of records that failed.
        duration_seconds: Total execution time.
        error_message: Error details if failed.
        started_at: Pipeline start timestamp.
        completed_at: Pipeline completion timestamp.
    """

    __tablename__ = "etl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Pipeline identification
    pipeline_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="running")

    # Metrics
    records_extracted: Mapped[int] = mapped_column(Integer, default=0)
    records_loaded: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.records_extracted
        if total == 0:
            return 0.0
        return (self.records_loaded / total) * 100

    @property
    def is_running(self) -> bool:
        """Check if pipeline is still running."""
        return self.status == "running"

    @property
    def is_success(self) -> bool:
        """Check if pipeline completed successfully."""
        return self.status == "success"

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<ETLRun(id={self.id}, pipeline='{self.pipeline_name}', "
            f"source='{self.source_name}', status='{self.status}')>"
        )
