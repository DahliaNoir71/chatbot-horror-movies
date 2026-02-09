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
        "ENVIRONMENT",
        "DEBUG",
        "TMDB_API_KEY",
        "KAGGLE_USERNAME",
        "KAGGLE_KEY",
        "POSTGRES_PASSWORD",
        "JWT_SECRET_KEY",
        # AI settings
        "LLM_MODEL_PATH",
        "LLM_CONTEXT_LENGTH",
        "LLM_MAX_TOKENS",
        "LLM_TEMPERATURE",
        "LLM_TIMEOUT_SECONDS",
        "LLM_N_GPU_LAYERS",
        "CLASSIFIER_MODEL_NAME",
        "CLASSIFIER_CONFIDENCE_THRESHOLD",
        "CLASSIFIER_DEVICE",
        "EMBEDDING_MODEL_NAME",
        "EMBEDDING_DIMENSIONS",
        "EMBEDDING_BATCH_SIZE",
        # Database
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_DB",
        "POSTGRES_VECTORS_DB",
        "DB_POOL_SIZE",
        "DB_POOL_OVERFLOW",
        "DB_POOL_TIMEOUT",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set all required environment variables for valid Settings."""
    # AI settings
    monkeypatch.setenv("LLM_MODEL_PATH", "models/test.gguf")
    monkeypatch.setenv("LLM_CONTEXT_LENGTH", "4096")
    monkeypatch.setenv("LLM_MAX_TOKENS", "512")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("LLM_N_GPU_LAYERS", "-1")
    monkeypatch.setenv("CLASSIFIER_MODEL_NAME", "MoritzLaurer/DeBERTa-v3-base-zeroshot-v2.0")
    monkeypatch.setenv("CLASSIFIER_CONFIDENCE_THRESHOLD", "0.4")
    monkeypatch.setenv("CLASSIFIER_DEVICE", "auto")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "384")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "64")
    # Database
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "horrorbot_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv("POSTGRES_DB", "horrorbot")
    monkeypatch.setenv("POSTGRES_VECTORS_DB", "horrorbot_vectors")
    monkeypatch.setenv("DB_POOL_SIZE", "5")
    monkeypatch.setenv("DB_POOL_OVERFLOW", "10")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "30")
    # Security
    monkeypatch.setenv("JWT_SECRET_KEY", "test_secret_key_that_is_longer_than_32_chars")
    # API sources
    monkeypatch.setenv("TMDB_API_KEY", "test_api_key")
    monkeypatch.setenv("KAGGLE_USERNAME", "test_user")
    monkeypatch.setenv("KAGGLE_KEY", "test_key")


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
        assert hasattr(settings, "llm")
        assert hasattr(settings, "classifier")
        assert hasattr(settings, "embedding")


@pytest.mark.usefixtures("clean_env")
class TestSettingsClass:
    """Tests for Settings class."""

    @staticmethod
    def test_can_create_with_valid_env(valid_env: None) -> None:
        """Settings can be created when all required variables are set."""
        s = Settings(_env_file=None)
        assert s.llm is not None
        assert s.classifier is not None
        assert s.embedding is not None
        assert s.database is not None

    @staticmethod
    def test_default_environment(valid_env: None) -> None:
        """Default environment is development."""
        s = Settings(_env_file=None)
        assert s.environment == "development"

    @staticmethod
    def test_valid_environments(valid_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid environment values are accepted."""
        for env in ["development", "production", "test"]:
            monkeypatch.setenv("ENVIRONMENT", env)
            s = Settings(_env_file=None)
            assert s.environment == env

    @staticmethod
    def test_environment_case_insensitive(valid_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment validation is case-insensitive."""
        monkeypatch.setenv("ENVIRONMENT", "PRODUCTION")
        s = Settings(_env_file=None)
        assert s.environment == "production"

    @staticmethod
    def test_invalid_environment(valid_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid environment raises ValidationError."""
        monkeypatch.setenv("ENVIRONMENT", "invalid")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    @staticmethod
    def test_debug_default_false(valid_env: None) -> None:
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
