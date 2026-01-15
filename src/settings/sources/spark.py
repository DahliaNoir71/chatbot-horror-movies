"""Spark Big Data configuration settings.

Source 5 (E1): Big Data processing with PySpark for C1/C2 validation.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.settings.base import get_project_root


class SparkSettings(BaseSettings):
    """Spark extraction configuration.

    Attributes:
        csv_path: Path to Kaggle horror movies CSV.
        app_name: Spark application name.
        master: Spark master URL (local mode by default).
        driver_memory: Spark driver memory allocation.
        shuffle_partitions: Number of shuffle partitions.
        min_votes: Minimum vote count filter.
        min_rating: Minimum rating filter.
    """

    # CSV source path
    csv_filename: str = Field(
        default="horror_movies.csv",
        alias="SPARK_CSV_FILENAME",
    )

    # Spark configuration
    app_name: str = Field(
        default="HorrorBot-ETL",
        alias="SPARK_APP_NAME",
    )
    master: str = Field(
        default="local[*]",
        alias="SPARK_MASTER",
    )
    driver_memory: str = Field(
        default="2g",
        alias="SPARK_DRIVER_MEMORY",
    )
    shuffle_partitions: int = Field(
        default=4,
        alias="SPARK_SHUFFLE_PARTITIONS",
    )
    ui_enabled: bool = Field(
        default=False,
        alias="SPARK_UI_ENABLED",
    )
    log_level: str = Field(
        default="WARN",
        alias="SPARK_LOG_LEVEL",
    )

    # Extraction filters
    min_votes: int = Field(
        default=50,
        alias="SPARK_MIN_VOTES",
    )
    min_rating: float = Field(
        default=0.0,
        alias="SPARK_MIN_RATING",
    )

    # Export settings
    export_format: str = Field(
        default="parquet",
        alias="SPARK_EXPORT_FORMAT",
    )
    batch_size: int = Field(
        default=1000,
        alias="SPARK_BATCH_SIZE",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------

    @property
    def csv_path(self) -> Path:
        """Full path to CSV file in raw data directory."""
        return get_project_root() / "data" / "raw" / "kaggle" / self.csv_filename

    @property
    def parquet_output_path(self) -> Path:
        """Output path for Parquet export."""
        return get_project_root() / "data" / "processed" / "spark"

    @property
    def checkpoint_path(self) -> Path:
        """Checkpoint path for Spark extraction."""
        return get_project_root() / "data" / "checkpoints" / "spark"

    @property
    def is_local_mode(self) -> bool:
        """Check if running in local mode."""
        return self.master.startswith("local")

    @property
    def spark_config(self) -> dict[str, str]:
        """Get Spark configuration as dictionary."""
        return {
            "spark.app.name": self.app_name,
            "spark.master": self.master,
            "spark.driver.memory": self.driver_memory,
            "spark.sql.shuffle.partitions": str(self.shuffle_partitions),
            "spark.ui.enabled": str(self.ui_enabled).lower(),
        }

    @property
    def java_home(self) -> str | None:
        """Get JAVA_HOME for Spark compatibility."""
        import os

        return os.getenv("JAVA_HOME")

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------

    @field_validator("min_votes")
    @classmethod
    def validate_min_votes(cls, v: int) -> int:
        """Validate minimum votes is non-negative."""
        if v < 0:
            raise ValueError("SPARK_MIN_VOTES must be >= 0")
        return v

    @field_validator("min_rating")
    @classmethod
    def validate_min_rating(cls, v: float) -> float:
        """Validate minimum rating is in valid range."""
        if v < 0.0 or v > 10.0:
            raise ValueError("SPARK_MIN_RATING must be between 0.0 and 10.0")
        return v

    @field_validator("driver_memory")
    @classmethod
    def validate_driver_memory(cls, v: str) -> str:
        """Validate driver memory format."""
        v_lower = v.lower()
        if not v_lower.endswith(("g", "m")):
            raise ValueError("SPARK_DRIVER_MEMORY must end with 'g' or 'm'")
        try:
            int(v_lower[:-1])
        except ValueError as err:
            raise ValueError("SPARK_DRIVER_MEMORY must be like '2g' or '512m'") from err
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate Spark log level."""
        valid_levels = {"ALL", "DEBUG", "ERROR", "FATAL", "INFO", "OFF", "TRACE", "WARN"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"SPARK_LOG_LEVEL must be one of {valid_levels}")
        return v_upper

    @field_validator("export_format")
    @classmethod
    def validate_export_format(cls, v: str) -> str:
        """Validate export format."""
        valid_formats = {"parquet", "csv", "json"}
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f"SPARK_EXPORT_FORMAT must be one of {valid_formats}")
        return v_lower
