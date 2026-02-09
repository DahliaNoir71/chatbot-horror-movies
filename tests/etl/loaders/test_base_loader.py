"""Unit tests for base loader and LoaderStats."""

from unittest.mock import MagicMock

import pytest
from pytest import approx

from src.etl.loaders.base import BaseLoader, LoaderStats


# -------------------------------------------------------------------------
# LoaderStats
# -------------------------------------------------------------------------


class TestLoaderStats:
    @staticmethod
    def test_defaults() -> None:
        stats = LoaderStats()
        assert stats.inserted == 0
        assert stats.updated == 0
        assert stats.skipped == 0
        assert stats.errors == 0
        assert stats.error_messages == []

    @staticmethod
    def test_total_processed() -> None:
        stats = LoaderStats(inserted=5, updated=3, skipped=2, errors=1)
        assert stats.total_processed == 11

    @staticmethod
    def test_total_processed_zero() -> None:
        assert LoaderStats().total_processed == 0

    @staticmethod
    def test_success_rate_no_errors() -> None:
        stats = LoaderStats(inserted=10, updated=5)
        assert stats.success_rate == approx(100.0)

    @staticmethod
    def test_success_rate_with_errors() -> None:
        stats = LoaderStats(inserted=8, errors=2)
        assert stats.success_rate == approx(80.0)

    @staticmethod
    def test_success_rate_all_errors() -> None:
        stats = LoaderStats(errors=10)
        assert stats.success_rate == approx(0.0)

    @staticmethod
    def test_success_rate_zero_processed() -> None:
        assert LoaderStats().success_rate == approx(100.0)

    @staticmethod
    def test_merge() -> None:
        s1 = LoaderStats(inserted=5, updated=3, errors=1, error_messages=["err1"])
        s2 = LoaderStats(inserted=10, updated=2, skipped=1, error_messages=["err2"])
        merged = s1.merge(s2)
        assert merged.inserted == 15
        assert merged.updated == 5
        assert merged.skipped == 1
        assert merged.errors == 1
        assert merged.error_messages == ["err1", "err2"]

    @staticmethod
    def test_merge_empty() -> None:
        s1 = LoaderStats(inserted=5)
        s2 = LoaderStats()
        merged = s1.merge(s2)
        assert merged.inserted == 5


# -------------------------------------------------------------------------
# BaseLoader (concrete subclass for testing)
# -------------------------------------------------------------------------


class ConcreteLoader(BaseLoader):
    name = "test"

    def load(self, data: object) -> LoaderStats:
        return self._stats


class TestBaseLoader:
    @staticmethod
    def test_init() -> None:
        session = MagicMock()
        loader = ConcreteLoader(session)
        assert loader.session is session
        assert loader.stats.inserted == 0

    @staticmethod
    def test_record_insert() -> None:
        loader = ConcreteLoader(MagicMock())
        loader._record_insert()
        assert loader.stats.inserted == 1

    @staticmethod
    def test_record_update() -> None:
        loader = ConcreteLoader(MagicMock())
        loader._record_update()
        assert loader.stats.updated == 1

    @staticmethod
    def test_record_skip() -> None:
        loader = ConcreteLoader(MagicMock())
        loader._record_skip()
        assert loader.stats.skipped == 1

    @staticmethod
    def test_record_error() -> None:
        loader = ConcreteLoader(MagicMock())
        loader._record_error("Something failed")
        assert loader.stats.errors == 1
        assert "Something failed" in loader.stats.error_messages

    @staticmethod
    def test_reset_stats() -> None:
        loader = ConcreteLoader(MagicMock())
        loader._record_insert()
        loader._record_insert()
        loader.reset_stats()
        assert loader.stats.inserted == 0

    @staticmethod
    def test_log_progress_no_error() -> None:
        loader = ConcreteLoader(MagicMock())
        loader._log_progress(100, 500)

    @staticmethod
    def test_log_summary_no_error() -> None:
        loader = ConcreteLoader(MagicMock())
        loader._log_summary()

    @staticmethod
    def test_load_returns_stats() -> None:
        loader = ConcreteLoader(MagicMock())
        result = loader.load(None)
        assert isinstance(result, LoaderStats)
