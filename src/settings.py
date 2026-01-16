"""Centralized configuration for HorrorBot project using Pydantic Settings.

All configuration values are sourced from environment variables (.env file).
No hardcoded defaults for sensitive values.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# PROJECT ROOT DETECTION
# =============================================================================

_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


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
        """ETL pipelines checkpoints."""
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
    """Logging configuration."""

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
            raise ValueError(f"Invalid LOG_LEVEL. Valid values: {valid_levels}")
        return v_upper


# =============================================================================
# ETL SETTINGS
# =============================================================================


class ETLSettings(BaseSettings):
    """ETL pipelines configuration."""

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


# =============================================================================
# SOURCE 1: TMDB (REST API)
# =============================================================================


class TMDBSettings(BaseSettings):
    """TMDB API configuration.

    Attributes:
        api_key: TMDB API key (required).
        base_url: TMDB API base URL.
        image_base_url: TMDB image CDN base URL.
        language: Language for API responses.
        horror_genre_id: TMDB genre ID for Horror (27).
    """

    api_key: str = Field(default="", alias="TMDB_API_KEY")
    base_url: str = Field(
        default="https://api.themoviedb.org/3",
        alias="TMDB_BASE_URL",
    )
    image_base_url: str = Field(
        default="https://image.tmdb.org/t/p/w500",
        alias="TMDB_IMAGE_BASE_URL",
    )

    # Extraction parameters
    language: str = Field(default="en-US", alias="TMDB_LANGUAGE")
    include_adult: bool = Field(default=True, alias="TMDB_INCLUDE_ADULT")
    horror_genre_id: int = Field(default=27, alias="TMDB_HORROR_GENRE_ID")

    # Year filters
    year_min: int = Field(default=2010, alias="TMDB_YEAR_MIN")
    year_max: int = Field(default=2025, alias="TMDB_YEAR_MAX")
    years_per_batch: int = Field(default=5, alias="TMDB_YEARS_PER_BATCH")
    use_period_batching: bool = Field(default=False, alias="TMDB_USE_PERIOD_BATCHING")

    # Rate limiting
    requests_per_period: int = Field(default=40, alias="TMDB_REQUESTS_PER_PERIOD")
    period_seconds: int = Field(default=10, alias="TMDB_PERIOD_SECONDS")
    min_request_delay: float = Field(default=0.25, alias="TMDB_MIN_REQUEST_DELAY")

    # Extraction
    default_max_pages: int = Field(default=500, alias="TMDB_MAX_PAGES")
    checkpoint_save_interval: int = Field(default=10, alias="TMDB_CHECKPOINT_SAVE_INTERVAL")
    enrich_movies: bool = Field(default=True, alias="TMDB_ENRICH_MOVIES")
    save_checkpoints: bool = Field(default=True, alias="TMDB_SAVE_CHECKPOINTS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Check if TMDB API key is configured."""
        return bool(self.api_key and self.api_key != "your_api_key_here")

    @property
    def requests_per_second(self) -> float:
        """Calculate requests per second from period settings."""
        if self.period_seconds <= 0:
            return 1.0
        return self.requests_per_period / self.period_seconds

    @field_validator("year_min")
    @classmethod
    def validate_year_min(cls, v: int) -> int:
        """Validate minimum year is plausible."""
        if v < 1888:
            raise ValueError("TMDB_YEAR_MIN must be >= 1888")
        if v > datetime.now().year:
            raise ValueError("TMDB_YEAR_MIN cannot be in the future")
        return v

    @field_validator("year_max")
    @classmethod
    def validate_year_max(cls, v: int) -> int:
        """Validate maximum year is plausible."""
        current_year = datetime.now().year
        if v > current_year:
            return current_year
        return v


# =============================================================================
# SOURCE 2: ROTTEN TOMATOES (WEB SCRAPING)
# =============================================================================


class RTSettings(BaseSettings):
    """Rotten Tomatoes scraping configuration.

    Attributes:
        base_url: RT website base URL.
        max_retries: Maximum retry attempts per request.
        timeout: Request timeout (seconds).
    """

    base_url: str = Field(
        default="https://www.rottentomatoes.com",
        alias="RT_BASE_URL",
    )
    max_retries: int = Field(default=3, alias="RT_MAX_RETRIES")
    timeout: int = Field(default=30, alias="RT_TIMEOUT")
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        alias="RT_USER_AGENT",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# =============================================================================
# SOURCE 4: KAGGLE / SPARK (BIG DATA)
# =============================================================================


class KaggleSettings(BaseSettings):
    """Kaggle dataset configuration.

    Attributes:
        username: Kaggle username.
        key: Kaggle API key.
        dataset_slug: Dataset identifier (user/dataset-name).
    """

    username: str = Field(default="", alias="KAGGLE_USERNAME")
    key: str = Field(default="", alias="KAGGLE_KEY")
    dataset_slug: str = Field(
        default="evangower/horror-movies",
        alias="KAGGLE_DATASET_SLUG",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Check if Kaggle credentials are configured."""
        return bool(self.username and self.key)


class SparkSettings(BaseSettings):
    """Apache Spark configuration for Big Data processing.

    Attributes:
        master: Spark master URL (local[*] for local mode).
        app_name: Spark application name.
        driver_memory: Driver memory allocation.
        executor_memory: Executor memory allocation.
    """

    master: str = Field(default="local[*]", alias="SPARK_MASTER")
    app_name: str = Field(default="HorrorBot-ETL", alias="SPARK_APP_NAME")
    driver_memory: str = Field(default="2g", alias="SPARK_DRIVER_MEMORY")
    executor_memory: str = Field(default="2g", alias="SPARK_EXECUTOR_MEMORY")
    shuffle_partitions: int = Field(default=4, alias="SPARK_SHUFFLE_PARTITIONS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# =============================================================================
# DATABASE SETTINGS (POSTGRESQL)
# =============================================================================


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration.

    Attributes:
        host: Database host.
        port: Database port.
        database: Database name.
        user: Database user.
        password: Database password.
        url: Full connection URL (overrides individual settings if provided).
    """

    host: str = Field(default="localhost", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    database: str = Field(default="horrorbot", alias="POSTGRES_DB")
    user: str = Field(default="horrorbot_user", alias="POSTGRES_USER")
    password: str = Field(default="", alias="POSTGRES_PASSWORD")
    url: str | None = Field(default=None, alias="DATABASE_URL")

    # Pool settings
    pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    pool_overflow: int = Field(default=10, alias="DB_POOL_OVERFLOW")
    pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Check if database credentials are configured."""
        return bool(self.password or self.url)

    @property
    def sync_url(self) -> str:
        """Generate synchronous PostgreSQL connection URL."""
        if self.url:
            return self.url
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def async_url(self) -> str:
        """Generate asynchronous PostgreSQL connection URL."""
        if self.url:
            return self.url.replace("postgresql://", "postgresql+asyncpg://")
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


# =============================================================================
# API SETTINGS (FASTAPI - E3)
# =============================================================================


class APISettings(BaseSettings):
    """FastAPI configuration for E3."""

    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT")
    reload: bool = Field(default=True, alias="API_RELOAD")
    workers: int = Field(default=4, alias="API_WORKERS")
    public_url: str = Field(default="http://localhost:8000", alias="API_PUBLIC_URL")
    title: str = Field(default="HorrorBot API", alias="API_TITLE")
    version: str = Field(default="1.0.0", alias="API_VERSION")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Dans SecuritySettings (lignes 388-406), ajouter après jwt_expire_minutes :


class SecuritySettings(BaseSettings):
    """JWT and rate limiting configuration for E3."""

    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, alias="JWT_EXPIRE_MINUTES")
    rate_limit_per_minute: int = Field(default=100, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, alias="RATE_LIMIT_PER_HOUR")

    # Demo authentication (format: "user1:pass1,user2:pass2")
    demo_users_raw: str = Field(default="", alias="AUTH_DEMO_USERS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Check if JWT secret is configured."""
        return bool(self.jwt_secret_key and len(self.jwt_secret_key) >= 32)

    @property
    def demo_users(self) -> dict[str, str]:
        """Parse demo users from 'user:pass,user:pass' format."""
        if not self.demo_users_raw:
            return {}
        users = {}
        for pair in self.demo_users_raw.split(","):
            if ":" in pair:
                username, password = pair.strip().split(":", 1)
                users[username.strip()] = password.strip()
        return users


class CORSSettings(BaseSettings):
    """CORS configuration for E3."""

    origins_raw: str = Field(
        default="http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def origins(self) -> list[str]:
        """Parse origins from comma-separated string."""
        return [o.strip() for o in self.origins_raw.split(",") if o.strip()]


# =============================================================================
# GLOBAL SETTINGS
# =============================================================================


class Settings(BaseSettings):
    """Global application settings.

    Aggregates all configuration sections into a single object.
    Access via the singleton: `from src.settings import settings`
    """

    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Paths and logging
    paths: PathsSettings = Field(default_factory=PathsSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    etl: ETLSettings = Field(default_factory=ETLSettings)

    # E1 Sources
    tmdb: TMDBSettings = Field(default_factory=TMDBSettings)
    rt: RTSettings = Field(default_factory=RTSettings)
    kaggle: KaggleSettings = Field(default_factory=KaggleSettings)
    spark: SparkSettings = Field(default_factory=SparkSettings)

    # Database
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    # E3 API
    api: APISettings = Field(default_factory=APISettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_envs = {"development", "production", "test"}
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"Invalid ENVIRONMENT. Valid values: {valid_envs}")
        return v_lower

    def model_post_init(self, _: Any) -> None:  # noqa: ARG002
        """Initialize directories after settings are loaded."""
        self.paths.ensure_directories()


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

settings = Settings()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_masked_settings() -> dict[str, Any]:
    """Return settings dict with sensitive values masked.

    Returns:
        Configuration dictionary safe for logging.
    """
    config = settings.model_dump()
    mask = "***MASKED***"

    # Paths to mask
    secrets = [
        ("tmdb", "api_key"),
        ("kaggle", "key"),
        ("database", "password"),
        ("database", "url"),
        ("security", "jwt_secret_key"),
    ]

    for section, key in secrets:
        if section in config and key in config[section] and config[section][key]:
            config[section][key] = mask

    return config


def print_sources_status() -> None:
    """Print configuration status for all E1 sources."""
    sources = [
        ("TMDB API", settings.tmdb.is_configured),
        ("Kaggle", settings.kaggle.is_configured),
        ("PostgreSQL", settings.database.is_configured),
    ]

    print("\n📊 E1 SOURCES STATUS:")
    print("-" * 40)
    for name, configured in sources:
        status = "✅" if configured else "❌"
        print(f"  {status} {name}")
    print("-" * 40)
