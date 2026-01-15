"""Kaggle dataset configuration settings.

Source 4 (E1): CSV datasets for Big Data processing.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    csv_filename: str = Field(
        default="horror_movies.csv",
        alias="KAGGLE_CSV_FILENAME",
    )
    batch_size: int = Field(
        default=1000,
        alias="KAGGLE_BATCH_SIZE",
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

    @property
    def csv_path(self) -> "Path":
        """Path to downloaded CSV file."""
        from src.settings.base import PathsSettings

        paths = PathsSettings()
        return paths.raw_dir / "kaggle" / self.csv_filename
