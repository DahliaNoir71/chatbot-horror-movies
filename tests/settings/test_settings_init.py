"""Tests for settings __init__.py module.

Covers: Settings class, get_masked_settings, print_sources_status
"""

import pytest
from pydantic import ValidationError

from src.settings import (
    Settings,
    get_masked_settings,
    print_sources_status,
    settings,
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove environment variables for isolated testing."""
    env_vars = [
        "ENVIRONMENT", "DEBUG",
        "TMDB_API_KEY", "KAGGLE_USERNAME", "KAGGLE_KEY",
        "POSTGRES_PASSWORD", "JWT_SECRET_KEY",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


class TestSettingsSingleton:
    """Tests for settings singleton instance."""

    @staticmethod
    def test_singleton_exists() -> None:
        """settings singleton is available."""
        assert settings is not None
        assert isinstance(settings, Settings)

    @staticmethod
    def test_singleton_has_subsettings() -> None:
        """settings has all expected sub-settings."""
        assert hasattr(settings, "tmdb")
        assert hasattr(settings, "database")
        assert hasattr(settings, "api")
        assert hasattr(settings, "paths")


@pytest.mark.usefixtures("clean_env")
class TestSettingsClass:
    """Tests for Settings class."""

    @staticmethod
    def test_default_environment() -> None:
        """Default environment is development."""
        s = Settings(_env_file=None)
        assert s.environment == "development"

    @staticmethod
    def test_valid_environments(monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid environment values are accepted."""
        for env in ["development", "production", "test"]:
            monkeypatch.setenv("ENVIRONMENT", env)
            s = Settings(_env_file=None)
            assert s.environment == env

    @staticmethod
    def test_environment_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment validation is case-insensitive."""
        monkeypatch.setenv("ENVIRONMENT", "PRODUCTION")
        s = Settings(_env_file=None)
        assert s.environment == "production"

    @staticmethod
    def test_invalid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid environment raises ValidationError."""
        monkeypatch.setenv("ENVIRONMENT", "invalid")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    @staticmethod
    def test_debug_default_false() -> None:
        """Debug is False by default."""
        s = Settings(_env_file=None)
        assert s.debug is False


class TestGetMaskedSettings:
    """Tests for get_masked_settings function."""

    @staticmethod
    def test_returns_dict() -> None:
        """get_masked_settings returns a dictionary."""
        result = get_masked_settings()
        assert isinstance(result, dict)

    @staticmethod
    def test_masks_sensitive_values() -> None:
        """Sensitive values are masked."""
        result = get_masked_settings()
        mask = "***MASKED***"

        if result.get("tmdb", {}).get("api_key"):
            assert result["tmdb"]["api_key"] == mask
        if result.get("database", {}).get("password"):
            assert result["database"]["password"] == mask
        if result.get("security", {}).get("jwt_secret_key"):
            assert result["security"]["jwt_secret_key"] == mask

    @staticmethod
    def test_preserves_non_sensitive_values() -> None:
        """Non-sensitive values are preserved."""
        result = get_masked_settings()
        assert result.get("environment") is not None
        assert result.get("tmdb", {}).get("base_url") is not None


class TestPrintSourcesStatus:
    """Tests for print_sources_status function."""

    @staticmethod
    def test_prints_without_error(capsys: pytest.CaptureFixture[str]) -> None:
        """print_sources_status runs without raising."""
        print_sources_status()
        captured = capsys.readouterr()
        assert "SOURCES STATUS" in captured.out

    @staticmethod
    def test_shows_source_names(capsys: pytest.CaptureFixture[str]) -> None:
        """Output includes expected source names."""
        print_sources_status()
        captured = capsys.readouterr()
        assert "TMDB" in captured.out
        assert "Kaggle" in captured.out
        assert "PostgreSQL" in captured.out
