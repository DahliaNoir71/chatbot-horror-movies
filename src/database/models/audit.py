"""Audit and compliance SQLAlchemy models.

Contains models for RGPD compliance (Article 30) and
ETL pipeline execution tracking.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, TimestampMixin


class RGPDProcessingRegistry(Base, TimestampMixin):
    """RGPD Article 30 processing registry.

    Documents all personal data processing activities
    as required by GDPR compliance.

    Attributes:
        id: Primary key.
        processing_name: Name of the processing activity.
        processing_purpose: Purpose description.
        data_categories: Types of data processed.
        data_subjects: Categories of individuals.
        retention_period: How long data is kept.
        legal_basis: Legal basis for processing.
    """

    __tablename__ = "rgpd_processing_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processing_name: Mapped[str] = mapped_column(String(255), nullable=False)
    processing_purpose: Mapped[str] = mapped_column(Text, nullable=False)

    # Data categories and subjects
    data_categories: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
    )
    data_subjects: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
    )
    recipients: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # Retention and security
    retention_period: Mapped[str] = mapped_column(String(100), nullable=False)
    security_measures: Mapped[str | None] = mapped_column(Text)

    # Legal basis
    legal_basis: Mapped[str] = mapped_column(String(100), nullable=False)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "legal_basis IN ("
            "'consent', 'contract', 'legal_obligation', "
            "'vital_interests', 'public_task', 'legitimate_interests')",
            name="chk_legal_basis",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<RGPDProcessingRegistry(id={self.id}, name='{self.processing_name}')>"


class DataRetentionLog(Base):
    """Audit log for data retention operations.

    Tracks all purge, anonymization, and archive operations
    performed for RGPD compliance.

    Attributes:
        id: Primary key.
        table_name: Target table.
        operation: Type of operation (purge, anonymize, archive).
        records_affected: Number of records processed.
        executed_at: Timestamp of execution.
    """

    __tablename__ = "data_retention_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    records_affected: Mapped[int] = mapped_column(Integer, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    executed_by: Mapped[str] = mapped_column(String(100), default="system")
    details: Mapped[dict | None] = mapped_column(JSONB)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<DataRetentionLog(table='{self.table_name}', "
            f"op='{self.operation}', records={self.records_affected})>"
        )


class ETLRun(Base):
    """ETL pipeline execution record.

    Tracks each pipeline run with statistics per source
    and overall status.

    Attributes:
        id: Primary key.
        run_id: Unique UUID for the run.
        status: Run status (running, completed, failed, partial).
        tmdb_count: Films extracted from TMDB.
        rt_count: Films scraped from RT.
        youtube_count: Videos extracted from YouTube.
        spark_count: Films enriched via Spark.
    """

    __tablename__ = "etl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        server_default=func.uuid_generate_v4(),
        unique=True,
        nullable=False,
    )

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Status
    status: Mapped[str] = mapped_column(String(20), default="running")

    # Statistics per source
    tmdb_count: Mapped[int] = mapped_column(Integer, default=0)
    rt_count: Mapped[int] = mapped_column(Integer, default=0)
    youtube_count: Mapped[int] = mapped_column(Integer, default=0)
    spark_count: Mapped[int] = mapped_column(Integer, default=0)

    # Total and errors
    total_films: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[dict | None] = mapped_column(JSONB)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'partial')",
            name="chk_etl_status",
        ),
    )

    @property
    def duration_seconds(self) -> float | None:
        """Calculate run duration in seconds."""
        if self.completed_at is None:
            return None
        delta = self.completed_at - self.started_at
        return delta.total_seconds()

    @property
    def is_successful(self) -> bool:
        """Check if run completed successfully."""
        return self.status == "completed"

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<ETLRun(id={self.id}, status='{self.status}', total={self.total_films})>"
