"""Rotten Tomatoes scraping configuration settings.

Source 2 (E1): Web scraping for critic scores.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RTSettings(BaseSettings):
    """Rotten Tomatoes scraping configuration.

    Attributes:
        base_url: RT website base URL.
        max_retries: Maximum retry attempts per request.
        timeout: Request timeout (seconds).
        user_agent: HTTP User-Agent for requests.
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
