"""RGPDProcessingRegistry model for GDPR compliance.

Tracks data processing activities as required by GDPR Article 30.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
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

    Attributes:
        id: Primary key.
        processing_name: Name of the processing activity.
        purpose: Purpose of data processing.
        data_categories: Categories of personal data processed.
        data_subjects: Categories of data subjects.
        recipients: Data recipients.
        retention_period: Data retention duration.
        legal_basis: Legal basis for processing.
        is_active: Whether processing is currently active.
    """

    __tablename__ = "rgpd_processing_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Processing identification
    processing_name: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)

    # Data description
    data_categories: Mapped[str] = mapped_column(Text, nullable=False)
    data_subjects: Mapped[str] = mapped_column(String(255), nullable=False)
    recipients: Mapped[str | None] = mapped_column(Text)

    # Retention and legal
    retention_period: Mapped[str] = mapped_column(String(100), nullable=False)
    legal_basis: Mapped[str] = mapped_column(String(100), nullable=False)

    # Security measures
    security_measures: Mapped[str | None] = mapped_column(Text)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

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
        return (
            f"<RGPDProcessingRegistry(id={self.id}, "
            f"name='{self.processing_name}', active={self.is_active})>"
        )
