"""Tests for data source settings.

Covers: imdb.py, kaggle.py, spark.py, tmdb.py, rotten_tomatoes.py
Uses monkeypatch to isolate from environment variables.
"""

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.settings.sources.imdb import IMDBSettings
from src.settings.sources.kaggle import KaggleSettings
from src.settings.sources.rotten_tomatoes import RTSettings
from src.settings.sources.spark import SparkSettings
from src.settings.sources.tmdb import TMDBSettings


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all relevant environment variables for isolated testing."""
    env_vars = [
        "IMDB_DB_PATH",
        "IMDB_BATCH_SIZE",
        "IMDB_MIN_VOTES",
        "IMDB_MIN_RATING",
        "KAGGLE_USERNAME",
        "KAGGLE_KEY",
        "KAGGLE_DATASET_SLUG",
        "KAGGLE_CSV_FILENAME",
        "KAGGLE_BATCH_SIZE",
        "RT_BASE_URL",
        "RT_MAX_RETRIES",
        "RT_TIMEOUT",
        "RT_USER_AGENT",
        "SPARK_CSV_FILENAME",
        "SPARK_APP_NAME",
        "SPARK_MASTER",
        "SPARK_DRIVER_MEMORY",
        "SPARK_SHUFFLE_PARTITIONS",
        "SPARK_UI_ENABLED",
        "SPARK_LOG_LEVEL",
        "SPARK_MIN_VOTES",
        "SPARK_MIN_RATING",
        "SPARK_EXPORT_FORMAT",
        "SPARK_BATCH_SIZE",
        "TMDB_API_KEY",
        "TMDB_BASE_URL",
        "TMDB_IMAGE_BASE_URL",
        "TMDB_LANGUAGE",
        "TMDB_INCLUDE_ADULT",
        "TMDB_HORROR_GENRE_ID",
        "TMDB_YEAR_MIN",
        "TMDB_YEAR_MAX",
        "TMDB_YEARS_PER_BATCH",
        "TMDB_USE_PERIOD_BATCHING",
        "TMDB_REQUESTS_PER_PERIOD",
        "TMDB_PERIOD_SECONDS",
        "TMDB_MIN_REQUEST_DELAY",
        "TMDB_MAX_PAGES",
        "TMDB_CHECKPOINT_SAVE_INTERVAL",
        "TMDB_ENRICH_MOVIES",
        "TMDB_SAVE_CHECKPOINTS",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def kaggle_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required Kaggle environment variables."""
    monkeypatch.setenv("KAGGLE_USERNAME", "test_user")
    monkeypatch.setenv("KAGGLE_KEY", "test_key")


@pytest.fixture
def tmdb_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required TMDB environment variables."""
    monkeypatch.setenv("TMDB_API_KEY", "test_api_key")


# =============================================================================
# IMDB.PY TESTS
# =============================================================================


@pytest.mark.usefixtures("clean_env")
class TestIMDBSettings:
    """Tests for IMDBSettings class."""

    @staticmethod
    def test_default_values() -> None:
        """Default IMDB settings are correct."""
        settings = IMDBSettings(_env_file=None)
        assert settings.batch_size == 1000
        assert settings.min_votes == 1000
        assert settings.min_rating == pytest.approx(0.0)

    @staticmethod
    def test_sqlite_path_property(monkeypatch: pytest.MonkeyPatch) -> None:
        """sqlite_path returns Path object."""
        monkeypatch.setenv("IMDB_DB_PATH", "data/test.db")
        settings = IMDBSettings(_env_file=None)
        assert isinstance(settings.sqlite_path, Path)
        assert settings.sqlite_path == Path("data/test.db")

    @staticmethod
    def test_is_configured_false_when_file_missing() -> None:
        """is_configured returns False when DB file doesn't exist."""
        settings = IMDBSettings(_env_file=None)
        assert settings.is_configured is False or settings.sqlite_path.exists()

    @staticmethod
    def test_is_configured_true_when_file_exists(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """is_configured returns True when DB file exists."""
        db_file = tmp_path / "test.db"
        db_file.touch()
        monkeypatch.setenv("IMDB_DB_PATH", str(db_file))
        settings = IMDBSettings(_env_file=None)
        assert settings.is_configured is True

    @staticmethod
    def test_connection_string_format(monkeypatch: pytest.MonkeyPatch) -> None:
        """connection_string returns valid SQLite URL."""
        monkeypatch.setenv("IMDB_DB_PATH", "data/imdb.db")
        settings = IMDBSettings(_env_file=None)
        assert settings.connection_string == "sqlite:///data/imdb.db"


# =============================================================================
# KAGGLE.PY TESTS
# =============================================================================


@pytest.mark.usefixtures("clean_env")
class TestKaggleSettings:
    """Tests for KaggleSettings class."""

    @staticmethod
    def test_missing_credentials() -> None:
        """Missing credentials raises ValidationError."""
        with pytest.raises(ValidationError):
            KaggleSettings(_env_file=None)

    @staticmethod
    def test_configured_values(kaggle_env_vars: None) -> None:
        """Default Kaggle settings are correct."""
        settings = KaggleSettings(_env_file=None)
        assert settings.dataset_slug == "evangower/horror-movies"
        assert settings.csv_filename == "horror_movies.csv"

    @staticmethod
    def test_is_configured_true_when_valid(kaggle_env_vars: None) -> None:
        """is_configured returns True when credentials are set."""
        settings = KaggleSettings(_env_file=None)
        assert settings.is_configured is True

    @staticmethod
    def test_csv_path_property(kaggle_env_vars: None) -> None:
        """csv_path returns correct path in raw directory."""
        settings = KaggleSettings(_env_file=None)
        path = settings.csv_path
        assert isinstance(path, Path)
        assert "kaggle" in str(path)


# =============================================================================
# ROTTEN_TOMATOES.PY TESTS
# =============================================================================


@pytest.mark.usefixtures("clean_env")
class TestRTSettings:
    """Tests for RTSettings class."""

    @staticmethod
    def test_default_values() -> None:
        """Default RT settings are correct."""
        settings = RTSettings(_env_file=None)
        assert settings.base_url == "https://www.rottentomatoes.com"
        assert settings.max_retries == 3
        assert settings.timeout == 30
        assert "Mozilla" in settings.user_agent


# =============================================================================
# SPARK.PY TESTS
# =============================================================================


@pytest.mark.usefixtures("clean_env")
class TestSparkSettings:
    """Tests for SparkSettings class."""

    @staticmethod
    def test_default_values() -> None:
        """Default Spark settings are correct."""
        settings = SparkSettings(_env_file=None)
        assert settings.app_name == "HorrorBot-ETL"
        assert settings.master == "local[*]"
        assert settings.driver_memory == "2g"

    @staticmethod
    def test_csv_path_property() -> None:
        """csv_path returns correct path."""
        settings = SparkSettings(_env_file=None)
        assert isinstance(settings.csv_path, Path)
        assert "kaggle" in str(settings.csv_path)

    @staticmethod
    def test_parquet_output_path_property() -> None:
        """parquet_output_path returns processed/spark path."""
        settings = SparkSettings(_env_file=None)
        path = settings.parquet_output_path
        assert "processed" in str(path)
        assert "spark" in str(path)

    @staticmethod
    def test_checkpoint_path_property() -> None:
        """checkpoint_path returns checkpoints/spark path."""
        settings = SparkSettings(_env_file=None)
        path = settings.checkpoint_path
        assert "checkpoints" in str(path)
        assert "spark" in str(path)

    @staticmethod
    def test_is_local_mode_true() -> None:
        """is_local_mode returns True for local master."""
        settings = SparkSettings(_env_file=None)
        assert settings.is_local_mode is True

    @staticmethod
    def test_is_local_mode_false(monkeypatch: pytest.MonkeyPatch) -> None:
        """is_local_mode returns False for cluster master."""
        monkeypatch.setenv("SPARK_MASTER", "spark://master:7077")
        settings = SparkSettings(_env_file=None)
        assert settings.is_local_mode is False

    @staticmethod
    def test_spark_config_property() -> None:
        """spark_config returns valid configuration dict."""
        settings = SparkSettings(_env_file=None)
        config = settings.spark_config
        assert isinstance(config, dict)
        assert config["spark.app.name"] == settings.app_name

    @staticmethod
    def test_validate_min_votes_negative(monkeypatch: pytest.MonkeyPatch) -> None:
        """Negative min_votes raises ValidationError."""
        monkeypatch.setenv("SPARK_MIN_VOTES", "-1")
        with pytest.raises(ValidationError):
            SparkSettings(_env_file=None)

    @staticmethod
    def test_validate_min_rating_out_of_range_low(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Negative min_rating raises ValidationError."""
        monkeypatch.setenv("SPARK_MIN_RATING", "-1.0")
        with pytest.raises(ValidationError):
            SparkSettings(_env_file=None)

    @staticmethod
    def test_validate_min_rating_out_of_range_high(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """min_rating > 10 raises ValidationError."""
        monkeypatch.setenv("SPARK_MIN_RATING", "11.0")
        with pytest.raises(ValidationError):
            SparkSettings(_env_file=None)

    @staticmethod
    def test_validate_driver_memory_invalid_suffix(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Invalid driver_memory suffix raises ValidationError."""
        monkeypatch.setenv("SPARK_DRIVER_MEMORY", "2k")
        with pytest.raises(ValidationError):
            SparkSettings(_env_file=None)

    @staticmethod
    def test_validate_driver_memory_invalid_format(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Invalid driver_memory format raises ValidationError."""
        monkeypatch.setenv("SPARK_DRIVER_MEMORY", "abcg")
        with pytest.raises(ValidationError):
            SparkSettings(_env_file=None)

    @staticmethod
    def test_validate_log_level_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid log level raises ValidationError."""
        monkeypatch.setenv("SPARK_LOG_LEVEL", "INVALID")
        with pytest.raises(ValidationError):
            SparkSettings(_env_file=None)

    @staticmethod
    def test_validate_export_format_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid export format raises ValidationError."""
        monkeypatch.setenv("SPARK_EXPORT_FORMAT", "xml")
        with pytest.raises(ValidationError):
            SparkSettings(_env_file=None)


# =============================================================================
# TMDB.PY TESTS
# =============================================================================


@pytest.mark.usefixtures("clean_env")
class TestTMDBSettings:
    """Tests for TMDBSettings class."""

    @staticmethod
    def test_missing_api_key() -> None:
        """Missing API key raises ValidationError."""
        with pytest.raises(ValidationError):
            TMDBSettings(_env_file=None)

    @staticmethod
    def test_configured_values(tmdb_env_vars: None) -> None:
        """Configured TMDB settings have correct values."""
        settings = TMDBSettings(_env_file=None)
        assert settings.base_url == "https://api.themoviedb.org/3"
        assert settings.horror_genre_id == 27
        assert settings.language == "en-US"

    @staticmethod
    def test_is_configured_false_when_placeholder(
        monkeypatch: pytest.MonkeyPatch, tmdb_env_vars: None
    ) -> None:
        """is_configured returns False for placeholder key."""
        monkeypatch.setenv("TMDB_API_KEY", "your_api_key_here")
        settings = TMDBSettings(_env_file=None)
        assert settings.is_configured is False

    @staticmethod
    def test_is_configured_true_when_valid(tmdb_env_vars: None) -> None:
        """is_configured returns True for valid API key."""
        settings = TMDBSettings(_env_file=None)
        assert settings.is_configured is True

    @staticmethod
    def test_requests_per_second_calculation(tmdb_env_vars: None) -> None:
        """requests_per_second calculates correctly."""
        settings = TMDBSettings(_env_file=None)
        assert settings.requests_per_second == pytest.approx(4.0)

    @staticmethod
    def test_requests_per_second_zero_period(
        monkeypatch: pytest.MonkeyPatch, tmdb_env_vars: None
    ) -> None:
        """requests_per_second returns 1.0 for zero period."""
        monkeypatch.setenv("TMDB_PERIOD_SECONDS", "0")
        settings = TMDBSettings(_env_file=None)
        assert settings.requests_per_second == pytest.approx(1.0)

    @staticmethod
    def test_validate_year_min_too_old(
        monkeypatch: pytest.MonkeyPatch, tmdb_env_vars: None
    ) -> None:
        """year_min before 1888 raises ValidationError."""
        monkeypatch.setenv("TMDB_YEAR_MIN", "1800")
        with pytest.raises(ValidationError):
            TMDBSettings(_env_file=None)

    @staticmethod
    def test_validate_year_min_future(monkeypatch: pytest.MonkeyPatch, tmdb_env_vars: None) -> None:
        """year_min in future raises ValidationError."""
        monkeypatch.setenv("TMDB_YEAR_MIN", "2100")
        with pytest.raises(ValidationError):
            TMDBSettings(_env_file=None)

    @staticmethod
    def test_validate_year_max_capped(monkeypatch: pytest.MonkeyPatch, tmdb_env_vars: None) -> None:
        """year_max in future is capped to current year."""
        monkeypatch.setenv("TMDB_YEAR_MAX", "2100")
        settings = TMDBSettings(_env_file=None)
        assert settings.year_max == datetime.now().year
