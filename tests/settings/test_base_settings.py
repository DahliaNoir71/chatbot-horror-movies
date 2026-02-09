"""Tests for base settings modules.

Covers: api.py, base.py, database.py
Uses monkeypatch to isolate from environment variables.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.settings.api import APISettings, CORSSettings, SecuritySettings
from src.settings.base import (
    ETLSettings,
    LoggingSettings,
    PathsSettings,
    get_env_file,
    get_project_root,
)
from src.settings.database import DatabaseSettings


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all relevant environment variables for isolated testing."""
    env_vars = [
        "LOG_LEVEL",
        "LOG_DIR",
        "LOG_FORMAT",
        "API_HOST",
        "API_PORT",
        "API_RELOAD",
        "API_WORKERS",
        "API_PUBLIC_URL",
        "API_TITLE",
        "API_VERSION",
        "JWT_SECRET_KEY",
        "JWT_ALGORITHM",
        "JWT_EXPIRE_MINUTES",
        "RATE_LIMIT_PER_MINUTE",
        "RATE_LIMIT_PER_HOUR",
        "CORS_ORIGINS",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_VECTORS_DB",
        "DB_POOL_SIZE",
        "DB_POOL_OVERFLOW",
        "DB_POOL_TIMEOUT",
        "ETL_MAX_WORKERS",
        "SCRAPING_DELAY",
        "USER_AGENT",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


# =============================================================================
# BASE.PY TESTS
# =============================================================================


class TestProjectRootFunctions:
    """Tests for module-level path functions."""

    @staticmethod
    def test_get_project_root_returns_path() -> None:
        """get_project_root returns a Path object."""
        root = get_project_root()
        assert isinstance(root, Path)
        assert root.exists()

    @staticmethod
    def test_get_env_file_returns_path() -> None:
        """get_env_file returns path to .env file."""
        env_file = get_env_file()
        assert isinstance(env_file, Path)
        assert env_file.name == ".env"


@pytest.mark.usefixtures("clean_env")
class TestPathsSettings:
    """Tests for PathsSettings class."""

    @staticmethod
    def test_project_root_property() -> None:
        """project_root returns valid path."""
        settings = PathsSettings(_env_file=None)
        assert isinstance(settings.project_root, Path)

    @staticmethod
    def test_data_directories_structure() -> None:
        """All data directory properties return correct paths."""
        settings = PathsSettings(_env_file=None)
        assert settings.data_dir == settings.project_root / "data"
        assert settings.raw_dir == settings.data_dir / "raw"
        assert settings.processed_dir == settings.data_dir / "processed"
        assert settings.checkpoints_dir == settings.data_dir / "checkpoints"

    @staticmethod
    def test_logs_dir_property() -> None:
        """logs_dir returns correct path."""
        settings = PathsSettings(_env_file=None)
        assert settings.logs_dir == settings.project_root / "logs"

    @staticmethod
    def test_ensure_directories_creates_dirs() -> None:
        """ensure_directories creates all required directories."""
        settings = PathsSettings(_env_file=None)
        settings.ensure_directories()
        assert settings.data_dir.exists()


@pytest.mark.usefixtures("clean_env")
class TestLoggingSettings:
    """Tests for LoggingSettings class."""

    @staticmethod
    def test_default_values() -> None:
        """Default logging settings are correct."""
        settings = LoggingSettings(_env_file=None)
        assert settings.level == "INFO"
        assert settings.format == "json"

    @staticmethod
    def test_validate_log_level_valid(monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid log levels are accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            monkeypatch.setenv("LOG_LEVEL", level)
            settings = LoggingSettings(_env_file=None)
            assert settings.level == level

    @staticmethod
    def test_validate_log_level_lowercase(monkeypatch: pytest.MonkeyPatch) -> None:
        """Lowercase log levels are uppercased."""
        monkeypatch.setenv("LOG_LEVEL", "debug")
        settings = LoggingSettings(_env_file=None)
        assert settings.level == "DEBUG"

    @staticmethod
    def test_validate_log_level_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid log levels raise ValidationError."""
        monkeypatch.setenv("LOG_LEVEL", "INVALID")
        with pytest.raises(ValidationError):
            LoggingSettings(_env_file=None)


@pytest.mark.usefixtures("clean_env")
class TestETLSettings:
    """Tests for ETLSettings class."""

    @staticmethod
    def test_default_values() -> None:
        """Default ETL settings are correct."""
        settings = ETLSettings(_env_file=None)
        assert settings.max_workers == 4
        assert settings.scraping_delay == pytest.approx(2.0)
        assert "HorrorBot" in settings.user_agent


# =============================================================================
# API.PY TESTS
# =============================================================================


@pytest.mark.usefixtures("clean_env")
class TestAPISettings:
    """Tests for APISettings class."""

    @staticmethod
    def test_default_values() -> None:
        """Default API settings are correct."""
        settings = APISettings(_env_file=None)
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.title == "HorrorBot API"


@pytest.mark.usefixtures("clean_env")
class TestSecuritySettings:
    """Tests for SecuritySettings class."""

    @staticmethod
    def test_missing_jwt_secret_key() -> None:
        """Missing JWT_SECRET_KEY raises ValidationError."""
        with pytest.raises(ValidationError):
            SecuritySettings(_env_file=None)

    @staticmethod
    def test_is_configured_false_when_short(monkeypatch: pytest.MonkeyPatch) -> None:
        """is_configured returns False when secret is too short."""
        monkeypatch.setenv("JWT_SECRET_KEY", "short")
        settings = SecuritySettings(_env_file=None)
        assert settings.is_configured is False

    @staticmethod
    def test_is_configured_true_when_valid(monkeypatch: pytest.MonkeyPatch) -> None:
        """is_configured returns True when secret is valid."""
        monkeypatch.setenv("JWT_SECRET_KEY", "a" * 32)
        settings = SecuritySettings(_env_file=None)
        assert settings.is_configured is True


@pytest.mark.usefixtures("clean_env")
class TestCORSSettings:
    """Tests for CORSSettings class."""

    @staticmethod
    def test_origins_single_value(monkeypatch: pytest.MonkeyPatch) -> None:
        """origins parses single origin correctly."""
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
        settings = CORSSettings(_env_file=None)
        assert settings.origins == ["http://localhost:3000"]

    @staticmethod
    def test_origins_multiple_values(monkeypatch: pytest.MonkeyPatch) -> None:
        """origins parses comma-separated origins."""
        monkeypatch.setenv("CORS_ORIGINS", "http://a.com,http://b.com")
        settings = CORSSettings(_env_file=None)
        assert settings.origins == ["http://a.com", "http://b.com"]

    @staticmethod
    def test_origins_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
        """origins strips whitespace from values."""
        monkeypatch.setenv("CORS_ORIGINS", "  http://a.com  ,  http://b.com  ")
        settings = CORSSettings(_env_file=None)
        assert settings.origins == ["http://a.com", "http://b.com"]

    @staticmethod
    def test_origins_empty_values_filtered(monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty values in origins are filtered out."""
        monkeypatch.setenv("CORS_ORIGINS", "http://a.com,,http://b.com,")
        settings = CORSSettings(_env_file=None)
        assert settings.origins == ["http://a.com", "http://b.com"]


# =============================================================================
# DATABASE.PY TESTS
# =============================================================================


@pytest.fixture
def db_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set all required database environment variables."""
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "horrorbot_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv("POSTGRES_DB", "horrorbot")
    monkeypatch.setenv("POSTGRES_VECTORS_DB", "horrorbot_vectors")
    monkeypatch.setenv("DB_POOL_SIZE", "5")
    monkeypatch.setenv("DB_POOL_OVERFLOW", "10")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "30")


@pytest.mark.usefixtures("clean_env")
class TestDatabaseSettings:
    """Tests for DatabaseSettings class."""

    @staticmethod
    def test_missing_required_fields() -> None:
        """Missing required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            DatabaseSettings(_env_file=None)

    @staticmethod
    def test_configured_values(db_env_vars: None) -> None:
        """Database settings with all values configured."""
        settings = DatabaseSettings(_env_file=None)
        assert settings.host == "localhost"
        assert settings.port == 5432
        assert settings.database == "horrorbot"
        assert settings.is_configured is True

    @staticmethod
    def test_sync_url_format(monkeypatch: pytest.MonkeyPatch, db_env_vars: None) -> None:
        """sync_url returns correct PostgreSQL URL."""
        monkeypatch.setenv("POSTGRES_HOST", "db.example.com")
        monkeypatch.setenv("POSTGRES_PORT", "5433")
        monkeypatch.setenv("POSTGRES_USER", "testuser")
        monkeypatch.setenv("POSTGRES_PASSWORD", "testpass")
        monkeypatch.setenv("POSTGRES_DB", "testdb")
        settings = DatabaseSettings(_env_file=None)
        expected = "postgresql://testuser:testpass@db.example.com:5433/testdb"
        assert settings.sync_url == expected

    @staticmethod
    def test_async_url_format(monkeypatch: pytest.MonkeyPatch, db_env_vars: None) -> None:
        """async_url returns correct asyncpg URL."""
        monkeypatch.setenv("POSTGRES_HOST", "db.example.com")
        monkeypatch.setenv("POSTGRES_PORT", "5433")
        monkeypatch.setenv("POSTGRES_USER", "testuser")
        monkeypatch.setenv("POSTGRES_PASSWORD", "testpass")
        monkeypatch.setenv("POSTGRES_DB", "testdb")
        settings = DatabaseSettings(_env_file=None)
        assert "postgresql+asyncpg://" in settings.async_url
        assert "testuser:testpass@db.example.com:5433/testdb" in settings.async_url

    @staticmethod
    def test_vectors_sync_url_format(monkeypatch: pytest.MonkeyPatch, db_env_vars: None) -> None:
        """vectors_sync_url returns correct URL for vectors DB."""
        monkeypatch.setenv("POSTGRES_USER", "user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "pass")
        monkeypatch.setenv("POSTGRES_VECTORS_DB", "vectors_db")
        settings = DatabaseSettings(_env_file=None)
        assert "vectors_db" in settings.vectors_sync_url

    @staticmethod
    def test_vectors_async_url_format(monkeypatch: pytest.MonkeyPatch, db_env_vars: None) -> None:
        """vectors_async_url returns correct asyncpg URL for vectors DB."""
        monkeypatch.setenv("POSTGRES_USER", "user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "pass")
        monkeypatch.setenv("POSTGRES_VECTORS_DB", "vectors_db")
        settings = DatabaseSettings(_env_file=None)
        assert "vectors_db" in settings.vectors_async_url
        assert "postgresql+asyncpg://" in settings.vectors_async_url
