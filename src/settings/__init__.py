"""Centralized configuration for HorrorBot project.

Configuration strategy (Hybrid approach):
- CRITICAL settings (AI, Database, Security): Require explicit .env configuration.
  No defaults. Raises ValidationError if missing.
- INFRASTRUCTURE settings (Logging, ETL, API ports): Can use safe defaults.
  Override via .env as needed.

All configuration values are sourced from environment variables (.env file).

Usage:
    from src.settings import settings

    # Access sub-settings
    settings.tmdb.api_key
    settings.database.sync_url
"""

from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.settings.ai import ClassifierSettings, EmbeddingSettings, LLMSettings
from src.settings.api import APISettings, CORSSettings, SecuritySettings
from src.settings.base import ETLSettings, LoggingSettings, PathsSettings
from src.settings.database import DatabaseSettings
from src.settings.sources import (
    KaggleSettings,
    RTSettings,
    SparkSettings,
    TMDBSettings,
)

__all__ = [
    # Main
    "Settings",
    "settings",
    # Base
    "PathsSettings",
    "LoggingSettings",
    "ETLSettings",
    # Database
    "DatabaseSettings",
    # API
    "APISettings",
    "SecuritySettings",
    "CORSSettings",
    # Sources
    "TMDBSettings",
    "RTSettings",
    "KaggleSettings",
    "SparkSettings",
    # AI (E2)
    "LLMSettings",
    "ClassifierSettings",
    "EmbeddingSettings",
    # Utilities
    "get_masked_settings",
    "print_sources_status",
]


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

    # E2 AI Services
    llm: LLMSettings = Field(default_factory=LLMSettings)
    classifier: ClassifierSettings = Field(default_factory=ClassifierSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)

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
            raise ValueError(f"Invalid ENVIRONMENT. Valid: {valid_envs}")
        return v_lower

    def model_post_init(self, _: Any) -> None:
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

    # Paths to mask (section, key)
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
