"""Kaggle dataset configuration settings.

Source 4 (E1): CSV datasets for Big Data processing.
"""

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Check if Kaggle credentials are configured."""
        return bool(self.username and self.key)
