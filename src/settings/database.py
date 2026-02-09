"""Database configuration settings.

PostgreSQL connection and pool settings for both databases:
- horrorbot: Relational data (films, credits, etc.)
- horrorbot_vectors: RAG embeddings store
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration.

    Manages connections to both horrorbot (relational) and
    horrorbot_vectors (RAG embeddings) databases.

    Attributes:
        host: Database host.
        port: Database port.
        user: Database user.
        password: Database password.
        database: Main database name (relational).
        vectors_database: Vectors database name (RAG).
    """

    host: str = Field(alias="POSTGRES_HOST")
    port: int = Field(alias="POSTGRES_PORT")
    user: str = Field(alias="POSTGRES_USER")
    password: str = Field(alias="POSTGRES_PASSWORD")

    # Database names
    database: str = Field(alias="POSTGRES_DB")
    vectors_database: str = Field(alias="POSTGRES_VECTORS_DB")

    # Pool settings
    pool_size: int = Field(alias="DB_POOL_SIZE")
    pool_overflow: int = Field(alias="DB_POOL_OVERFLOW")
    pool_timeout: int = Field(alias="DB_POOL_TIMEOUT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Check if database credentials are configured."""
        return bool(self.password)

    # -------------------------------------------------------------------------
    # Main Database (horrorbot) URLs
    # -------------------------------------------------------------------------

    @property
    def sync_url(self) -> str:
        """Synchronous PostgreSQL URL for main database."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def async_url(self) -> str:
        """Asynchronous PostgreSQL URL for main database."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    # -------------------------------------------------------------------------
    # Vectors Database (horrorbot_vectors) URLs
    # -------------------------------------------------------------------------

    @property
    def vectors_sync_url(self) -> str:
        """Synchronous PostgreSQL URL for vectors database."""
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.vectors_database}"
        )

    @property
    def vectors_async_url(self) -> str:
        """Asynchronous PostgreSQL URL for vectors database."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.vectors_database}"
        )
