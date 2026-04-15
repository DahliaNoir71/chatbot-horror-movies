"""RGPDProcessingRegistry model for GDPR compliance.

Tracks data processing activities as required by GDPR Article 30.
"""

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class RGPDProcessingRegistry(Base):
    """RGPD processing registry entry.

    Documents data processing activities for GDPR compliance.
    Schema aligned with docker/init-db/02_horrorbot_schema.sql.

    Attributes:
        id: Primary key.
        processing_name: Name of the processing activity.
        processing_purpose: Purpose of data processing.
        data_categories: Categories of personal data processed.
        data_subjects: Categories of data subjects.
        recipients: Data recipients.
        retention_period: Data retention duration.
        legal_basis: Legal basis for processing.
        security_measures: Description of security measures.
    """

    __tablename__ = "rgpd_processing_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Processing identification
    processing_name: Mapped[str] = mapped_column(String(255), nullable=False)
    processing_purpose: Mapped[str] = mapped_column(Text, nullable=False)

    # Data description (PostgreSQL TEXT[] arrays)
    data_categories: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    data_subjects: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    recipients: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # Retention and legal
    retention_period: Mapped[str] = mapped_column(String(100), nullable=False)
    legal_basis: Mapped[str] = mapped_column(String(100), nullable=False)

    # Security measures
    security_measures: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<RGPDProcessingRegistry(id={self.id}, name='{self.processing_name}')>"
