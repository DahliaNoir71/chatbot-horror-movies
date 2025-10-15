"""
Configuration unifiée pour le projet HorrorBot.
Utilise Pydantic Settings pour charger depuis .env avec validation automatique.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Détecter le chemin du .env (à la racine du projet)
ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    """Configuration globale unifiée pour HorrorBot."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # ENVIRONNEMENT
    # =========================================================================
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    # =========================================================================
    # TMDB API
    # =========================================================================
    tmdb_api_key: str = Field(default="", description="Clé API TMDB")
    tmdb_base_url: str = Field(default="https://api.themoviedb.org/3")
    tmdb_image_base_url: str = Field(default="https://image.tmdb.org/t/p/w500")

    # Paramètres TMDB
    tmdb_horror_genre_id: int = Field(default=27)
    tmdb_requests_per_period: int = Field(default=40)
    tmdb_period_seconds: int = Field(default=10)
    tmdb_language: str = Field(default="en-US")
    tmdb_include_adult: bool = Field(default=True)
    tmdb_default_max_pages: Optional[int] = Field(default=None)
    tmdb_enrich_movies: bool = Field(default=True)
    tmdb_save_checkpoints: bool = Field(default=True)
    tmdb_checkpoint_save_interval: int = Field(default=10)

    @computed_field
    @property
    def tmdb_min_request_delay(self) -> float:
        """Délai minimal entre requêtes TMDB."""
        return self.tmdb_period_seconds / self.tmdb_requests_per_period

    # =========================================================================
    # POSTGRESQL - Base principale
    # =========================================================================
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="horrorbot")
    postgres_user: str = Field(default="horrorbot_user")
    postgres_password: str = Field(default="")

    @computed_field
    @property
    def database_url(self) -> str:
        """URL de connexion PostgreSQL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # =========================================================================
    # POSTGRESQL - Base IMDb externe
    # =========================================================================
    imdb_postgres_host: str = Field(default="localhost")
    imdb_postgres_port: int = Field(default=5433)
    imdb_postgres_db: str = Field(default="imdb_subset")
    imdb_postgres_user: str = Field(default="imdb_reader")
    imdb_postgres_password: str = Field(default="")

    @computed_field
    @property
    def imdb_database_url(self) -> str:
        """URL de connexion PostgreSQL IMDb."""
        return (
            f"postgresql://{self.imdb_postgres_user}:{self.imdb_postgres_password}"
            f"@{self.imdb_postgres_host}:{self.imdb_postgres_port}/{self.imdb_postgres_db}"
        )

    # =========================================================================
    # WIKIPEDIA
    # =========================================================================
    wikipedia_base_url: str = Field(default="https://en.wikipedia.org")
    wikipedia_user_agent: str = Field(default="HorrorBot/1.0 (Educational Project)")
    wikipedia_request_timeout: int = Field(default=30)
    wikipedia_rate_limit_delay: float = Field(default=1.0)
    wikipedia_max_retries: int = Field(default=3)
    wikipedia_min_title_length: int = Field(default=2)
    wikipedia_start_year: int = Field(default=1900)
    wikipedia_end_year: int = Field(default=2025)
    wikipedia_max_films: int = Field(default=50)
    wikipedia_cache_expiry_days: int = Field(default=7)
    wikipedia_save_checkpoints: bool = Field(default=True)

    # =========================================================================
    # SPARK
    # =========================================================================
    spark_home: str = Field(default="/opt/spark")
    spark_master: str = Field(default="local[4]")
    spark_driver_memory: str = Field(default="4g")
    spark_executor_memory: str = Field(default="4g")
    spark_parquet_path: str = Field(default="data/big_data/movies_large.parquet")
    spark_app_name: str = Field(default="HorrorBotExtractor")
    spark_default_parallelism: int = Field(default=4)

    # =========================================================================
    # API REST
    # =========================================================================
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000)
    api_reload: bool = Field(default=True)
    api_workers: int = Field(default=4)
    api_public_url: str = Field(default="http://localhost:8000")

    # JWT
    jwt_secret_key: str = Field(default="")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=30)

    # Rate limiting
    rate_limit_per_minute: int = Field(default=100)
    rate_limit_per_hour: int = Field(default=1000)

    # CORS
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:8000")

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # =========================================================================
    # CHEMINS
    # =========================================================================
    data_raw_dir: str = Field(default="data/raw")
    data_processed_dir: str = Field(default="data/processed")
    data_checkpoints_dir: str = Field(default="data/checkpoints")
    log_dir: str = Field(default="logs")

    @computed_field
    @property
    def raw_dir(self) -> Path:
        """Chemin absolu vers data/raw."""
        path = Path(self.data_raw_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @computed_field
    @property
    def processed_dir(self) -> Path:
        """Chemin absolu vers data/processed."""
        path = Path(self.data_processed_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @computed_field
    @property
    def checkpoints_dir(self) -> Path:
        """Chemin absolu vers data/checkpoints."""
        path = Path(self.data_checkpoints_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @computed_field
    @property
    def logs_dir(self) -> Path:
        """Chemin absolu vers logs/."""
        path = Path(self.log_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # =========================================================================
    # ETL
    # =========================================================================
    etl_max_workers: int = Field(default=4)
    scraping_delay: float = Field(default=2.0)
    user_agent: str = Field(default="HorrorBot-ETL/1.0 (Educational Project)")

    # =========================================================================
    # VALIDATION
    # =========================================================================
    @field_validator("tmdb_api_key")
    def validate_tmdb_api_key(self, v: str) -> str:
        """Valide que la clé API TMDB n'est pas vide."""
        if not v:
            raise ValueError(
                "TMDB_API_KEY manquante. "
                "Obtenir une clé sur https://www.themoviedb.org/settings/api"
            )
        return v


# =========================================================================
# CLASSES D'ACCÈS PRATIQUE (pour compatibilité avec ancien code)
# =========================================================================


class TMDBConfig:
    """Wrapper pour accès style settings.tmdb.api_key"""

    def __init__(self, settings_obj: Settings) -> None:
        self._settings = settings_obj

    @property
    def api_key(self) -> str:
        return self._settings.tmdb_api_key

    @property
    def base_url(self) -> str:
        return self._settings.tmdb_base_url

    @property
    def image_base_url(self) -> str:
        return self._settings.tmdb_image_base_url

    @property
    def horror_genre_id(self) -> int:
        return self._settings.tmdb_horror_genre_id

    @property
    def requests_per_period(self) -> int:
        return self._settings.tmdb_requests_per_period

    @property
    def period_seconds(self) -> int:
        return self._settings.tmdb_period_seconds

    @property
    def language(self) -> str:
        return self._settings.tmdb_language

    @property
    def include_adult(self) -> bool:
        return self._settings.tmdb_include_adult

    @property
    def default_max_pages(self) -> Optional[int]:
        return self._settings.tmdb_default_max_pages

    @property
    def enrich_movies(self) -> bool:
        return self._settings.tmdb_enrich_movies

    @property
    def save_checkpoints(self) -> bool:
        return self._settings.tmdb_save_checkpoints

    @property
    def checkpoint_save_interval(self) -> int:
        return self._settings.tmdb_checkpoint_save_interval

    @property
    def min_request_delay(self) -> float:
        return self._settings.tmdb_min_request_delay


class WikipediaConfig:
    """Wrapper pour accès style settings.wikipedia.base_url"""

    def __init__(self, settings_obj: Settings) -> None:
        self._settings = settings_obj

    @property
    def base_url(self) -> str:
        return self._settings.wikipedia_base_url

    @property
    def user_agent(self) -> str:
        return self._settings.wikipedia_user_agent

    @property
    def request_timeout(self) -> int:
        return self._settings.wikipedia_request_timeout

    @property
    def rate_limit_delay(self) -> float:
        return self._settings.wikipedia_rate_limit_delay

    @property
    def max_retries(self) -> int:
        return self._settings.wikipedia_max_retries

    @property
    def start_year(self) -> int:
        return self._settings.wikipedia_start_year

    @property
    def end_year(self) -> int:
        return self._settings.wikipedia_end_year

    @property
    def max_films(self) -> int:
        return self._settings.wikipedia_max_films

    @property
    def save_checkpoints(self) -> bool:
        return self._settings.wikipedia_save_checkpoints


class PathsConfig:
    """Wrapper pour accès style settings.paths.checkpoints_dir"""

    def __init__(self, settings_obj: Settings) -> None:
        self._settings = settings_obj

    @property
    def raw_dir(self) -> Path:
        return self._settings.raw_dir

    @property
    def processed_dir(self) -> Path:
        return self._settings.processed_dir

    @property
    def checkpoints_dir(self) -> Path:
        return self._settings.checkpoints_dir

    @property
    def logs_dir(self) -> Path:
        return self._settings.logs_dir


class SettingsWrapper:
    """Wrapper pour compatibilité avec l'ancien code"""

    def __init__(self, settings_obj: Settings) -> None:
        self._settings = settings_obj
        self.tmdb = TMDBConfig(settings_obj)
        self.wikipedia = WikipediaConfig(settings_obj)
        self.paths = PathsConfig(settings_obj)

    def __getattr__(self, name: str) -> object:
        """Fallback pour accès direct aux attributs"""
        return getattr(self._settings, name)


# Instance globale
_settings_obj = Settings()
settings = SettingsWrapper(_settings_obj)

# Debug
if not ENV_FILE.exists():
    print(f"⚠️ Fichier .env introuvable à : {ENV_FILE.absolute()}")
else:
    print(f"✅ Fichier .env chargé depuis : {ENV_FILE.absolute()}")
