"""Apache Spark configuration settings.

Source 5 (E1): Big Data processing with SparkSQL.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
