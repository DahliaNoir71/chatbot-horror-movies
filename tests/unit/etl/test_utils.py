"""Tests unitaires pour utils."""

import pytest
from pathlib import Path

from src.etl.utils import (
    CheckpointManager,
    clean_text,
    truncate_text,
    is_valid_year
)


@pytest.mark.unit
class TestCheckpointManager:
    """Tests CheckpointManager."""

    @pytest.fixture
    def manager(self, tmp_data_dir: Path) -> CheckpointManager:
        """Manager avec répertoire temporaire."""
        return CheckpointManager(tmp_data_dir / "checkpoints")

    @staticmethod
    def test_save_checkpoint(manager: CheckpointManager) -> None:
        """Test sauvegarde."""
        data = {"movies": [{"id": 1}], "count": 1}

        path = manager.save("test", data)

        assert path.exists()
        assert path.name == "test.json"

    @staticmethod
    def test_load_checkpoint(manager: CheckpointManager) -> None:
        """Test chargement."""
        data = {"movies": [{"id": 1}]}
        manager.save("test", data)
        loaded = manager.load("test")
        assert loaded == data

    @staticmethod
    def test_load_nonexistent(manager: CheckpointManager) -> None:
        """Test chargement fichier inexistant."""
        loaded = manager.load("nonexistent")
        assert loaded is None


@pytest.mark.unit
class TestTextUtils:
    """Tests utilitaires texte."""

    @staticmethod
    def test_clean_text() -> None:
        """Test nettoyage de texte."""
        dirty = "Text   with    spaces\nand newlines"
        clean = clean_text(dirty)
        assert "  " not in clean
        assert "\n" not in clean

    @staticmethod
    def test_truncate_text_long() -> None:
        """Test troncature de texte long."""
        text = "A" * 150
        truncated = truncate_text(text, 100)
        assert len(truncated) == 100
        assert truncated.endswith("...")

    @staticmethod
    def test_is_valid_year() -> None:
        """Test validation d'année."""
        assert is_valid_year(1980) is True
        assert is_valid_year(1800) is False
        assert is_valid_year(3000) is False
