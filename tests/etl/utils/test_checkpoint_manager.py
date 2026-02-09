"""Unit tests for checkpoint manager."""

from pathlib import Path

import pytest

from src.etl.utils.checkpoint_manager import CheckpointManager


@pytest.fixture()
def manager(tmp_path: Path) -> CheckpointManager:
    return CheckpointManager(checkpoint_dir=tmp_path, prefix="test")


class TestSaveAndLoad:
    @staticmethod
    def test_save_returns_path(manager: CheckpointManager) -> None:
        path = manager.save("extraction", {"page": 5})
        assert path.exists()
        assert path.suffix == ".json"

    @staticmethod
    def test_roundtrip(manager: CheckpointManager) -> None:
        manager.save("extraction", {"page": 5, "total": 100})
        loaded = manager.load("extraction")
        assert loaded is not None
        assert loaded["data"]["page"] == 5
        assert loaded["data"]["total"] == 100

    @staticmethod
    def test_timestamp_added(manager: CheckpointManager) -> None:
        manager.save("extraction", {"page": 1})
        loaded = manager.load("extraction")
        assert "timestamp" in loaded

    @staticmethod
    def test_load_nonexistent_returns_none(manager: CheckpointManager) -> None:
        assert manager.load("nonexistent") is None

    @staticmethod
    def test_overwrite(manager: CheckpointManager) -> None:
        manager.save("state", {"v": 1})
        manager.save("state", {"v": 2})
        loaded = manager.load("state")
        assert loaded["data"]["v"] == 2


class TestDelete:
    @staticmethod
    def test_delete_existing(manager: CheckpointManager) -> None:
        manager.save("temp", {"x": 1})
        assert manager.delete("temp") is True
        assert manager.load("temp") is None

    @staticmethod
    def test_delete_nonexistent(manager: CheckpointManager) -> None:
        assert manager.delete("nonexistent") is False


class TestExists:
    @staticmethod
    def test_exists_true(manager: CheckpointManager) -> None:
        manager.save("state", {"x": 1})
        assert manager.exists("state") is True

    @staticmethod
    def test_exists_false(manager: CheckpointManager) -> None:
        assert manager.exists("nonexistent") is False


class TestBuildPath:
    @staticmethod
    def test_safe_name_slashes(manager: CheckpointManager) -> None:
        path = manager._build_path("a/b\\c")
        assert "/" not in path.name.replace("\\", "")
        assert path.name == "test_a_b_c.json"

    @staticmethod
    def test_prefix_used(manager: CheckpointManager) -> None:
        path = manager._build_path("state")
        assert path.name.startswith("test_")


class TestBuildCheckpointData:
    @staticmethod
    def test_wraps_data() -> None:
        result = CheckpointManager._build_checkpoint_data({"key": "value"})
        assert "timestamp" in result
        assert result["data"] == {"key": "value"}


class TestInit:
    @staticmethod
    def test_default_dir_created(tmp_path: Path) -> None:
        custom_dir = tmp_path / "custom" / "checkpoints"
        mgr = CheckpointManager(checkpoint_dir=custom_dir)
        assert custom_dir.exists()
        assert mgr.checkpoint_dir == custom_dir

    @staticmethod
    def test_custom_prefix(tmp_path: Path) -> None:
        mgr = CheckpointManager(checkpoint_dir=tmp_path, prefix="etl")
        path = mgr._build_path("test")
        assert path.name.startswith("etl_")
