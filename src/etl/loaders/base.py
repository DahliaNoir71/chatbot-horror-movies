"""Base loader abstract class.

Provides common interface and utilities for all
ETL loaders inserting data into PostgreSQL.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.etl.utils.logger import setup_logger


@dataclass
class LoaderStats:
    """Statistics for a loader operation.

    Attributes:
        inserted: Number of new records inserted.
        updated: Number of existing records updated.
        skipped: Number of records skipped (duplicates).
        errors: Number of failed records.
        error_messages: List of error descriptions.
    """

    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        """Total records processed."""
        return self.inserted + self.updated + self.skipped + self.errors

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage.

        Returns:
            Success rate between 0.0 and 100.0.
        """
        if self.total_processed == 0:
            return 100.0
        failed = self.errors
        return round((1 - failed / self.total_processed) * 100, 2)

    def merge(self, other: "LoaderStats") -> "LoaderStats":
        """Merge statistics from another LoaderStats.

        Args:
            other: LoaderStats to merge.

        Returns:
            New LoaderStats with combined values.
        """
        return LoaderStats(
            inserted=self.inserted + other.inserted,
            updated=self.updated + other.updated,
            skipped=self.skipped + other.skipped,
            errors=self.errors + other.errors,
            error_messages=self.error_messages + other.error_messages,
        )


class BaseLoader(ABC):
    """Abstract base class for all ETL loaders.

    Provides common functionality for database operations,
    logging, and statistics tracking.

    Attributes:
        name: Loader identifier for logging.
    """

    name: str = "base"

    def __init__(self, session: Session) -> None:
        """Initialize loader with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session
        self._logger = setup_logger(f"etl.loader.{self.name}")
        self._stats = LoaderStats()

    @property
    def session(self) -> Session:
        """Get the SQLAlchemy session."""
        return self._session

    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self._logger

    @property
    def stats(self) -> LoaderStats:
        """Get current loader statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset statistics for a new load operation."""
        self._stats = LoaderStats()

    @abstractmethod
    def load(self, data: object) -> LoaderStats:
        """Execute the load operation.

        Args:
            data: Data to load (type depends on implementation).

        Returns:
            LoaderStats with operation results.
        """
        pass

    def _record_insert(self) -> None:
        """Record a successful insert."""
        self._stats.inserted += 1

    def _record_update(self) -> None:
        """Record a successful update."""
        self._stats.updated += 1

    def _record_skip(self) -> None:
        """Record a skipped record."""
        self._stats.skipped += 1

    def _record_error(self, message: str) -> None:
        """Record an error with message.

        Args:
            message: Error description.
        """
        self._stats.errors += 1
        self._stats.error_messages.append(message)
        self._logger.warning(message)

    def _log_progress(self, current: int, total: int) -> None:
        """Log loading progress at 100-item intervals.

        Args:
            current: Current item count.
            total: Total items to process.
        """
        if total > 0 and current % 100 == 0:
            pct = (current / total) * 100
            self._logger.info(f"Progress: {current}/{total} ({pct:.1f}%)")

    def _log_summary(self) -> None:
        """Log final statistics summary."""
        self._logger.info(
            f"{self.name} complete: "
            f"inserted={self._stats.inserted}, "
            f"updated={self._stats.updated}, "
            f"skipped={self._stats.skipped}, "
            f"errors={self._stats.errors}"
        )
