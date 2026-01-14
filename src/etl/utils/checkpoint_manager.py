"""Checkpoint management for resumable ETL operations."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.etl.utils.logger import setup_logger


class CheckpointManager:
    """Manage ETL pipeline checkpoints for resumable operations.

    Saves extraction state to JSON files for recovery after interruption.
    """

    def __init__(
        self,
        checkpoint_dir: Path | None = None,
        prefix: str = "checkpoint",
    ) -> None:
        """Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory for checkpoint files.
            prefix: Prefix for checkpoint filenames.
        """
        self._checkpoint_dir = checkpoint_dir or Path("data/checkpoints")
        self._prefix = prefix
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._logger = setup_logger("etl.checkpoint")

    @property
    def checkpoint_dir(self) -> Path:
        """Return checkpoint directory path."""
        return self._checkpoint_dir

    def save(self, name: str, data: dict[str, Any]) -> Path:
        """Save checkpoint data to JSON file.

        Args:
            name: Checkpoint identifier.
            data: Data to persist.

        Returns:
            Path to saved checkpoint file.
        """
        checkpoint_path = self._build_path(name)
        checkpoint_data = self._build_checkpoint_data(data)

        self._write_json(checkpoint_path, checkpoint_data)
        self._logger.debug(f"Checkpoint saved: {checkpoint_path.name}")

        return checkpoint_path

    def load(self, name: str) -> dict[str, Any] | None:
        """Load checkpoint data from JSON file.

        Args:
            name: Checkpoint identifier.

        Returns:
            Checkpoint data or None if not found.
        """
        checkpoint_path = self._build_path(name)

        if not checkpoint_path.exists():
            return None

        data = self._read_json(checkpoint_path)
        self._logger.debug(f"Checkpoint loaded: {checkpoint_path.name}")

        return data

    def delete(self, name: str) -> bool:
        """Delete checkpoint file.

        Args:
            name: Checkpoint identifier.

        Returns:
            True if deleted, False if not found.
        """
        checkpoint_path = self._build_path(name)

        if not checkpoint_path.exists():
            return False

        checkpoint_path.unlink()
        self._logger.debug(f"Checkpoint deleted: {checkpoint_path.name}")
        return True

    def exists(self, name: str) -> bool:
        """Check if checkpoint exists.

        Args:
            name: Checkpoint identifier.

        Returns:
            True if checkpoint file exists.
        """
        return self._build_path(name).exists()

    def _build_path(self, name: str) -> Path:
        """Build checkpoint file path.

        Args:
            name: Checkpoint identifier.

        Returns:
            Full path to checkpoint file.
        """
        safe_name = name.replace("/", "_").replace("\\", "_")
        return self._checkpoint_dir / f"{self._prefix}_{safe_name}.json"

    @staticmethod
    def _build_checkpoint_data(data: dict[str, Any]) -> dict[str, Any]:
        """Wrap data with metadata.

        Args:
            data: Original data.

        Returns:
            Data with timestamp metadata.
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        """Write data to JSON file.

        Args:
            path: Target file path.
            data: Data to serialize.
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        """Read data from JSON file.

        Args:
            path: Source file path.

        Returns:
            Deserialized data.
        """
        with open(path, encoding="utf-8") as f:
            return json.load(f)
