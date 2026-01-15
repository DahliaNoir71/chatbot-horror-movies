"""IMDB SQLite database configuration settings.

Source 4 (E1): SQLite database for C2 SQL queries validation.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IMDBSettings(BaseSettings):
    """IMDB SQLite database configuration.

    Uses imdb-sqlite package to generate local SQLite DB
    from official IMDB TSV datasets.

    Attributes:
        db_path: Path to SQLite database file.
        batch_size: Rows per batch for extraction.
        min_votes: Minimum votes filter for quality.
        min_rating: Minimum rating filter.
    """

    db_path: str = Field(
        default="data/raw/imdb/imdb.db",
        alias="IMDB_DB_PATH",
    )
    batch_size: int = Field(
        default=1000,
        alias="IMDB_BATCH_SIZE",
    )
    min_votes: int = Field(
        default=1000,
        alias="IMDB_MIN_VOTES",
    )
    min_rating: float = Field(
        default=0.0,
        alias="IMDB_MIN_RATING",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlite_path(self) -> Path:
        """Get SQLite database path as Path object.

        Returns:
            Path to SQLite database file.
        """
        return Path(self.db_path)

    @property
    def is_configured(self) -> bool:
        """Check if IMDB database exists.

        Returns:
            True if database file exists.
        """
        return self.sqlite_path.exists()

    @property
    def connection_string(self) -> str:
        """Get SQLite connection string.

        Returns:
            SQLAlchemy-compatible connection URI.
        """
        return f"sqlite:///{self.db_path}"
