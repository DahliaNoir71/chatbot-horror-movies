"""Base extractor abstract class.

Provides common interface and utilities for all
ETL extractors.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from src.etl.types import ETLCheckpoint, ETLResult


class BaseExtractor(ABC):
    """Abstract base class for all ETL extractors.

    Provides common functionality for checkpoint management,
    logging, and result tracking.

    Attributes:
        name: Extractor identifier (e.g., 'tmdb', 'youtube').
        logger: Logger instance for this extractor.
    """

    name: str = "base"

    def __init__(self) -> None:
        """Initialize base extractor."""
        self._logger = logging.getLogger(f"etl.{self.name}")
        self._start_time: datetime | None = None
        self._extracted_count: int = 0
        self._errors: list[str] = []

    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self._logger

    @abstractmethod
    def extract(self, **kwargs: object) -> ETLResult:
        """Execute the extraction process.

        Args:
            **kwargs: Extractor-specific parameters.

        Returns:
            ETLResult with extraction statistics.
        """
        pass

    def _start_extraction(self) -> None:
        """Mark the start of extraction."""
        self._start_time = datetime.now()
        self._extracted_count = 0
        self._errors = []
        self._logger.info(f"Starting {self.name} extraction")

    def _end_extraction(self) -> ETLResult:
        """Mark the end of extraction and return result.

        Returns:
            ETLResult with final statistics.
        """
        duration = self._calculate_duration()
        success = len(self._errors) == 0

        self._logger.info(
            f"Completed {self.name} extraction: {self._extracted_count} items in {duration:.2f}s"
        )

        return ETLResult(
            source=self.name,
            success=success,
            count=self._extracted_count,
            errors=self._errors if self._errors else [],
            duration_seconds=duration,
        )

    def _calculate_duration(self) -> float:
        """Calculate extraction duration in seconds."""
        if self._start_time is None:
            return 0.0
        delta = datetime.now() - self._start_time
        return delta.total_seconds()

    def _log_error(self, message: str) -> None:
        """Log and track an error.

        Args:
            message: Error message to log.
        """
        self._logger.error(message)
        self._errors.append(message)

    def _log_progress(self, current: int, total: int) -> None:
        """Log extraction progress.

        Args:
            current: Current item count.
            total: Total expected items.
        """
        if total > 0:
            percentage = (current / total) * 100
            self._logger.info(f"Progress: {current}/{total} ({percentage:.1f}%)")

    # -------------------------------------------------------------------------
    # Checkpoint Management
    # -------------------------------------------------------------------------

    def save_checkpoint(self, checkpoint: ETLCheckpoint, path: Path) -> None:
        """Save checkpoint to file.

        Args:
            checkpoint: Checkpoint data to save.
            path: File path for checkpoint.
        """
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)
        self._logger.debug(f"Checkpoint saved: {path}")

    def load_checkpoint(self, path: Path) -> ETLCheckpoint | None:
        """Load checkpoint from file.

        Args:
            path: File path to load from.

        Returns:
            Checkpoint data or None if not found.
        """
        import json

        if not path.exists():
            return None

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._logger.info(f"Checkpoint loaded: {path}")
            return ETLCheckpoint(**data)
        except (json.JSONDecodeError, TypeError) as e:
            self._logger.warning(f"Invalid checkpoint file: {e}")
            return None

    def delete_checkpoint(self, path: Path) -> None:
        """Delete checkpoint file.

        Args:
            path: File path to delete.
        """
        if path.exists():
            path.unlink()
            self._logger.debug(f"Checkpoint deleted: {path}")

    def create_checkpoint(
        self,
        last_page: int | None = None,
        last_year: int | None = None,
        last_id: int | str | None = None,
        processed_ids: list[int] | None = None,
    ) -> ETLCheckpoint:
        """Create a checkpoint with current state.

        Args:
            last_page: Last processed page number.
            last_year: Last processed year.
            last_id: Last processed item ID.
            processed_ids: List of processed IDs.

        Returns:
            ETLCheckpoint with current timestamp.
        """
        checkpoint: ETLCheckpoint = {
            "source": self.name,
            "timestamp": datetime.now().isoformat(),
        }

        if last_page is not None:
            checkpoint["last_page"] = last_page
        if last_year is not None:
            checkpoint["last_year"] = last_year
        if last_id is not None:
            checkpoint["last_id"] = last_id
        if processed_ids is not None:
            checkpoint["processed_ids"] = processed_ids

        return checkpoint
