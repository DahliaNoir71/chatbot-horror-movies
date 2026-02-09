"""Unit tests for ETL logger setup."""

import logging
from pathlib import Path

from src.etl.utils.logger import (
    _LOGGERS_CACHE,
    _create_console_handler,
    _create_file_handler,
    _get_log_file_path,
    setup_logger,
)


class TestSetupLogger:
    @staticmethod
    def test_returns_logger() -> None:
        logger = setup_logger("test.logger.unique1")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.logger.unique1"

    @staticmethod
    def test_has_handlers() -> None:
        logger = setup_logger("test.logger.unique2")
        assert len(logger.handlers) >= 1

    @staticmethod
    def test_level_set() -> None:
        logger = setup_logger("test.logger.unique3", level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    @staticmethod
    def test_cache_returns_same_instance() -> None:
        logger1 = setup_logger("test.logger.cached")
        logger2 = setup_logger("test.logger.cached")
        assert logger1 is logger2

    @staticmethod
    def test_propagate_disabled() -> None:
        logger = setup_logger("test.logger.unique4")
        assert logger.propagate is False

    @staticmethod
    def test_cached() -> None:
        name = "test.logger.cache_check"
        setup_logger(name)
        assert name in _LOGGERS_CACHE


class TestCreateConsoleHandler:
    @staticmethod
    def test_returns_stream_handler() -> None:
        formatter = logging.Formatter("%(message)s")
        handler = _create_console_handler(formatter, logging.INFO)
        assert isinstance(handler, logging.StreamHandler)

    @staticmethod
    def test_level_set() -> None:
        formatter = logging.Formatter("%(message)s")
        handler = _create_console_handler(formatter, logging.WARNING)
        assert handler.level == logging.WARNING

    @staticmethod
    def test_formatter_set() -> None:
        formatter = logging.Formatter("%(message)s")
        handler = _create_console_handler(formatter, logging.INFO)
        assert handler.formatter is formatter


class TestCreateFileHandler:
    @staticmethod
    def test_returns_file_handler(tmp_path: Path) -> None:
        formatter = logging.Formatter("%(message)s")
        handler = _create_file_handler("test", formatter, logging.INFO, tmp_path)
        assert isinstance(handler, logging.FileHandler)
        handler.close()

    @staticmethod
    def test_level_set(tmp_path: Path) -> None:
        formatter = logging.Formatter("%(message)s")
        handler = _create_file_handler("test", formatter, logging.WARNING, tmp_path)
        assert handler.level == logging.WARNING
        handler.close()


class TestGetLogFilePath:
    @staticmethod
    def test_creates_directory(tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        path = _get_log_file_path("test.name", log_dir)
        assert log_dir.exists()
        assert path.parent == log_dir

    @staticmethod
    def test_filename_format(tmp_path: Path) -> None:
        path = _get_log_file_path("etl.tmdb", tmp_path)
        assert path.name.startswith("etl_tmdb_")
        assert path.suffix == ".log"

    @staticmethod
    def test_dots_replaced_in_name(tmp_path: Path) -> None:
        path = _get_log_file_path("a.b.c", tmp_path)
        assert "a_b_c" in path.name

    @staticmethod
    def test_default_dir_when_none() -> None:
        path = _get_log_file_path("test", None)
        assert path.parent == Path("logs")
