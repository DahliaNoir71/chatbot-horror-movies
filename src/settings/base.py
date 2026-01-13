"""Base configuration settings.

Contains foundational settings for paths, logging, and ETL.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# PROJECT ROOT DETECTION
# =============================================================================

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


def get_project_root() -> Path:
    """Get project root directory."""
    return _PROJECT_ROOT


def get_env_file() -> Path:
    """Get .env file path."""
    return _ENV_FILE


# =============================================================================
# PATH SETTINGS
# =============================================================================


class PathsSettings(BaseSettings):
    """Data and logs paths configuration.

    Automatically creates required directories on initialization.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def project_root(self) -> Path:
        """Project root directory."""
        return _PROJECT_ROOT

    @property
    def data_dir(self) -> Path:
        """Root data directory."""
        return _PROJECT_ROOT / "data"

    @property
    def raw_dir(self) -> Path:
        """Raw data from sources (CSV, JSON)."""
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        """Processed and aggregated data."""
        return self.data_dir / "processed"

    @property
    def checkpoints_dir(self) -> Path:
        """ETL pipeline checkpoints."""
        return self.data_dir / "checkpoints"

    @property
    def logs_dir(self) -> Path:
        """Application logs."""
        return _PROJECT_ROOT / "logs"

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        directories = [
            self.data_dir,
            self.raw_dir,
            self.processed_dir,
            self.checkpoints_dir,
            self.logs_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# =============================================================================
# LOGGING SETTINGS
# =============================================================================


class LoggingSettings(BaseSettings):
    """Logging configuration.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Log files directory.
        format: Log format (json or text).
    """

    level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: str = Field(default="logs", alias="LOG_DIR")
    format: str = Field(default="json", alias="LOG_FORMAT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid LOG_LEVEL. Valid: {valid_levels}")
        return v_upper


# =============================================================================
# ETL SETTINGS
# =============================================================================


class ETLSettings(BaseSettings):
    """ETL pipeline configuration.

    Attributes:
        max_workers: Maximum parallel workers.
        scraping_delay: Delay between scraping requests (seconds).
        user_agent: HTTP User-Agent for scraping.
    """

    max_workers: int = Field(default=4, alias="ETL_MAX_WORKERS")
    scraping_delay: float = Field(default=2.0, alias="SCRAPING_DELAY")
    user_agent: str = Field(
        default="HorrorBot-ETL/1.0 (Educational Project)",
        alias="USER_AGENT",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
