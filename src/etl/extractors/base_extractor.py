"""Abstract base class for all data extractors."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ExtractionMetrics:
    """Standardized extraction metrics."""

    source_name: str
    total_records: int = 0
    failed_records: int = 0
    start_time: datetime | None = None
    end_time: datetime | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Calculate extraction duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_records == 0:
            return 0.0
        successful = self.total_records - self.failed_records
        return (successful / self.total_records) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "source_name": self.source_name,
            "total_records": self.total_records,
            "failed_records": self.failed_records,
            "success_rate": round(self.success_rate, 2),
            "duration_seconds": round(self.duration_seconds, 2),
            "errors_count": len(self.errors),
        }

    def reset(self) -> None:
        """Reset metrics for new extraction run."""
        self.total_records = 0
        self.failed_records = 0
        self.start_time = None
        self.end_time = None
        self.errors.clear()


class BaseExtractor(ABC):
    """Abstract base class defining contract for all extractors.

    All extractors must implement:
        - extract(): Main extraction method
        - validate_config(): Configuration validation

    Provides:
        - Metrics tracking (duration, success rate, errors)
        - Logger instance
        - Helper methods for extraction lifecycle
    """

    def __init__(self, source_name: str) -> None:
        """Initialize extractor with logging and metrics.

        Args:
            source_name: Name of the data source.
        """
        self.source_name = source_name
        self.metrics = ExtractionMetrics(source_name=source_name)
        self.logger = logging.getLogger(f"etl.{source_name.lower()}")

    @abstractmethod
    def extract(
        self,
        *,
        file_path: str | None = None,
        limit: int | None = None,
        file_pattern: str | None = None,
        **kwargs: str | int | float | bool | None,
    ) -> list[dict[str, str | int | float | bool | list[str] | None]]:
        """Extract data from the source.

        Args:
            file_path: Optional path to the file to process
            limit: Optional maximum number of records to extract
            file_pattern: Optional pattern for file matching (e.g., "*.csv")
            **kwargs: Additional extractor-specific parameters.

        Returns:
            List of dictionaries where keys are strings and values can be:
            - str: For text data
            - int: For integer values
            - float: For decimal numbers
            - bool: For boolean flags
            - list[str]: For multiple values (e.g., genres, tags)
            - None: For missing or null values

        Raises:
            Exception: On extraction failure.
        """

    @abstractmethod
    def validate_config(self) -> None:
        """Validate extractor configuration.

        Raises:
            ValueError: If configuration is invalid.
        """

    def _start_extraction(self) -> None:
        """Initialize metrics at extraction start."""
        self.metrics.reset()
        self.metrics.start_time = datetime.now()
        self.logger.info(f"extraction_started: {self.source_name}")

    def _end_extraction(self) -> None:
        """Finalize metrics at extraction end."""
        self.metrics.end_time = datetime.now()
        self.logger.info(
            f"extraction_ended: {self.source_name} "
            f"({self.metrics.total_records} records, "
            f"{self.metrics.duration_seconds:.2f}s)"
        )

    def _record_error(self, error_msg: str) -> None:
        """Record an error in metrics.

        Args:
            error_msg: Error message to record.
        """
        self.metrics.errors.append(error_msg)
        self.metrics.failed_records += 1
        self.logger.warning(f"extraction_error: {error_msg}")

    def _increment_records(self, count: int = 1) -> None:
        """Increment total records count.

        Args:
            count: Number of records to add.
        """
        self.metrics.total_records += count

    def get_stats(self) -> dict[str, Any]:
        """Get extraction statistics.

        Returns:
            Dictionary with extraction metrics.
        """
        return self.metrics.to_dict()
