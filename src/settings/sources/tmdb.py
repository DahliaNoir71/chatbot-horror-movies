"""TMDB API configuration settings.

Source 1 (E1): REST API for movie metadata.
"""

from datetime import datetime

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    checkpoint_save_interval: int = Field(
        default=10,
        alias="TMDB_CHECKPOINT_SAVE_INTERVAL",
    )
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
