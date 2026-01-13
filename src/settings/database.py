"""Database configuration settings.

PostgreSQL connection and pool settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration.

    Attributes:
        host: Database host.
        port: Database port.
        database: Database name.
        user: Database user.
        password: Database password.
        url: Full connection URL (overrides individual settings).
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
