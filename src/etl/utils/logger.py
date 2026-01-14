"""ETL logging configuration with file and console handlers."""

import logging
import sys
from datetime import datetime
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_LOG_DATE_FORMAT = "%H:%M:%S"
_LOGGERS_CACHE: dict[str, logging.Logger] = {}


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_dir: Path | None = None,
) -> logging.Logger:
    """Configure and return a logger with file and console handlers.

    Args:
        name: Logger name (e.g., 'etl.tmdb').
        level: Logging level (default INFO).
        log_dir: Directory for log files. If None, uses 'logs/'.

    Returns:
        Configured logger instance.
    """
    if name in _LOGGERS_CACHE:
        return _LOGGERS_CACHE[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, _LOG_DATE_FORMAT)

    console_handler = _create_console_handler(formatter, level)
    logger.addHandler(console_handler)

    file_handler = _create_file_handler(name, formatter, level, log_dir)
    if file_handler:
        logger.addHandler(file_handler)

    _LOGGERS_CACHE[name] = logger
    return logger


def _create_console_handler(
    formatter: logging.Formatter,
    level: int,
) -> logging.StreamHandler:
    """Create console stream handler.

    Args:
        formatter: Log formatter.
        level: Logging level.

    Returns:
        Configured StreamHandler.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def _create_file_handler(
    name: str,
    formatter: logging.Formatter,
    level: int,
    log_dir: Path | None,
) -> logging.FileHandler | None:
    """Create file handler with daily rotation.

    Args:
        name: Logger name for filename.
        formatter: Log formatter.
        level: Logging level.
        log_dir: Directory for log files.

    Returns:
        Configured FileHandler or None on failure.
    """
    try:
        log_path = _get_log_file_path(name, log_dir)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setLevel(level)
        handler.setFormatter(formatter)
        return handler
    except OSError as e:
        print(f"Warning: Could not create log file: {e}", file=sys.stderr)
        return None


def _get_log_file_path(name: str, log_dir: Path | None) -> Path:
    """Build log file path with date suffix.

    Args:
        name: Logger name.
        log_dir: Base directory for logs.

    Returns:
        Full path to log file.
    """
    if log_dir is None:
        log_dir = Path("logs")

    log_dir.mkdir(parents=True, exist_ok=True)

    safe_name = name.replace(".", "_").replace("/", "_")
    date_suffix = datetime.now().strftime("%Y%m%d")
    filename = f"{safe_name}_{date_suffix}.log"

    return log_dir / filename
