"""Configuration centralisée du projet HorrorBot avec Pydantic Settings."""

from datetime import datetime
from pathlib import Path
from typing import Any

# ✅ Chargement explicite du .env AVANT tout le reste
from dotenv import load_dotenv

# Trouve le .env à la racine du projet (2 niveaux au-dessus de ce fichier)
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)

from pydantic import Field, field_validator  # noqa: E402
from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: E402


# === Chemins du projet ===


class PathsSettings(BaseSettings):
    """Configuration des chemins de données et logs."""

    raw_dir: Path = Field(default=Path("data/raw"), alias="DATA_RAW_DIR")
    processed_dir: Path = Field(
        default=Path("data/processed"), alias="DATA_PROCESSED_DIR"
    )
    checkpoints_dir: Path = Field(
        default=Path("data/checkpoints"), alias="DATA_CHECKPOINTS_DIR"
    )
    logs_dir: Path = Field(default=Path("logs"), alias="LOG_DIR")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("raw_dir", "processed_dir", "checkpoints_dir", "logs_dir")
    @classmethod
    def create_directories(cls, v: Path) -> Path:
        """Crée les répertoires s'ils n'existent pas."""
        v.mkdir(parents=True, exist_ok=True)
        return v


# === Configuration TMDB ===


class TMDBSettings(BaseSettings):
    """Configuration API TMDB."""

    api_key: str = Field(..., alias="TMDB_API_KEY")
    base_url: str = Field(default="https://api.themoviedb.org/3", alias="TMDB_BASE_URL")
    image_base_url: str = Field(
        default="https://image.tmdb.org/t/p/w500", alias="TMDB_IMAGE_BASE_URL"
    )

    # Paramètres d'extraction
    language: str = Field(default="en-US", alias="TMDB_LANGUAGE")
    include_adult: bool = Field(default=False, alias="TMDB_INCLUDE_ADULT")
    horror_genre_id: int = Field(default=27, alias="TMDB_HORROR_GENRE_ID")

    # ✅ Filtres temporels
    year_min: int = Field(default=1960, alias="TMDB_YEAR_MIN")
    year_max: int = Field(default=datetime.now().year, alias="TMDB_YEAR_MAX")
    years_per_batch: int = Field(default=5, alias="TMDB_YEARS_PER_BATCH")

    # Rate limiting
    requests_per_period: int = 40
    period_seconds: int = 10
    min_request_delay: float = 0.25
    use_period_batching: bool = Field(
        default=False, alias="TMDB_USE_PERIOD_BATCHING"
    )  # ✅

    # Extraction
    default_max_pages: int = Field(default=5, alias="TMDB_MAX_PAGES")
    checkpoint_save_interval: int = 10
    enrich_movies: bool = False
    save_checkpoints: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Valide que la clé API est définie."""
        if not v or v == "your_api_key_here":
            raise ValueError(
                "TMDB_API_KEY invalide. Obtenir une clé sur "
                "https://www.themoviedb.org/settings/api"
            )
        return v

    @field_validator("year_min")
    @classmethod
    def validate_year_min(cls, v: int) -> int:
        """Valide que l'année minimale est plausible."""
        current_year = datetime.now().year
        if v < 1888:
            raise ValueError("TMDB_YEAR_MIN doit être >= 1888")
        if v > current_year:
            raise ValueError(
                f"TMDB_YEAR_MIN ne peut pas être dans le futur (année courante: {current_year})"
            )
        return v

    @field_validator("year_max")
    @classmethod
    def validate_year_max(cls, v: int, values: dict[str, Any]) -> int:
        """Valide que l'année maximale est plausible par rapport à l'année minimale."""
        current_year = datetime.now().year
        year_min = values.data.get("year_min", 1900)

        if v < year_min:
            raise ValueError(
                f"TMDB_YEAR_MAX ({v}) ne peut pas être inférieur à TMDB_YEAR_MIN ({year_min})"
            )

        if v > current_year:
            raise ValueError(
                f"TMDB_YEAR_MAX ne peut pas être dans le futur (année courante: {current_year})"
            )

        return v

    @field_validator("years_per_batch")
    @classmethod
    def validate_years_per_batch(cls, v: int) -> int:
        """Valide que years_per_batch est raisonnable."""
        if not 1 <= v <= 10:
            raise ValueError("TMDB_YEARS_PER_BATCH doit être entre 1 et 10")
        return v


# === Configuration PostgreSQL ===


class DatabaseSettings(BaseSettings):
    """Configuration PostgreSQL principale."""

    host: str = Field(default="localhost", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    database: str = Field(default="horrorbot", alias="POSTGRES_DB")
    user: str = Field(default="horrorbot_user", alias="POSTGRES_USER")
    password: str = Field(default="", alias="POSTGRES_PASSWORD")
    url: str | None = Field(default=None, alias="DATABASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def connection_url(self) -> str:
        """Génère l'URL de connexion PostgreSQL."""
        if self.url:
            return self.url
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class IMDbDatabaseSettings(BaseSettings):
    """Configuration PostgreSQL externe IMDb (pour extraction C1)."""

    host: str = Field(default="localhost", alias="IMDB_POSTGRES_HOST")
    port: int = Field(default=5433, alias="IMDB_POSTGRES_PORT")
    database: str = Field(default="imdb_subset", alias="IMDB_POSTGRES_DB")
    user: str = Field(default="imdb_reader", alias="IMDB_POSTGRES_USER")
    password: str = Field(default="", alias="IMDB_POSTGRES_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def connection_url(self) -> str:
        """Génère l'URL de connexion PostgreSQL IMDb."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


# === Configuration API REST ===


class APISettings(BaseSettings):
    """Configuration FastAPI."""

    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT")
    reload: bool = Field(default=True, alias="API_RELOAD")
    workers: int = Field(default=4, alias="API_WORKERS")
    public_url: str = Field(default="http://localhost:8000", alias="API_PUBLIC_URL")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# === Configuration Sécurité ===


class SecuritySettings(BaseSettings):
    """Configuration JWT et rate limiting."""

    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, alias="JWT_EXPIRE_MINUTES")
    rate_limit_per_minute: int = Field(default=100, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, alias="RATE_LIMIT_PER_HOUR")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Valide que la clé JWT est définie et sécurisée."""
        if not v or "generate_" in v.lower():
            raise ValueError(
                "JWT_SECRET_KEY invalide. Générer avec: openssl rand -hex 32"
            )
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY trop courte (minimum 32 caractères)")
        return v


# === Configuration CORS ===


class CORSSettings(BaseSettings):
    """Configuration CORS."""

    origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def origins(self) -> list[str]:
        """Parse et retourne la liste des origines."""
        return [origin.strip() for origin in self.origins_raw.split(",")]


# === Configuration ETL ===


class ETLSettings(BaseSettings):
    """Configuration pipeline ETL."""

    max_workers: int = Field(default=4, alias="ETL_MAX_WORKERS")
    scraping_delay: float = Field(default=2.0, alias="SCRAPING_DELAY")
    user_agent: str = Field(
        default="HorrorBot-ETL/1.0 (Educational Project)", alias="USER_AGENT"
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# === Configuration Logging ===


class LoggingSettings(BaseSettings):
    """Configuration logs."""

    level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: Path = Field(default=Path("logs"), alias="LOG_DIR")
    format: str = Field(default="json", alias="LOG_FORMAT")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Valide le niveau de log."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL invalide. Valeurs: {valid_levels}")
        return v_upper


# === Configuration Globale ===


class Settings(BaseSettings):
    """Configuration globale de l'application."""

    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    paths: PathsSettings = Field(default_factory=PathsSettings)
    tmdb: TMDBSettings = Field(default_factory=TMDBSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    imdb_database: IMDbDatabaseSettings = Field(default_factory=IMDbDatabaseSettings)
    api: APISettings = Field(default_factory=APISettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    etl: ETLSettings = Field(default_factory=ETLSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Valide l'environnement."""
        valid_envs = {"development", "production", "test"}
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"ENVIRONMENT invalide. Valeurs: {valid_envs}")
        return v_lower


# === Instance singleton ===

settings = Settings()


# === Utilitaire pour afficher la config (debug) ===


def print_settings() -> dict[str, Any]:
    """Affiche la configuration (sans secrets) pour debug."""
    config_dict = settings.model_dump()

    masked = "***MASKED***"

    # Masquer les secrets
    if "tmdb" in config_dict and "api_key" in config_dict["tmdb"]:
        config_dict["tmdb"]["api_key"] = masked
    if "database" in config_dict and "password" in config_dict["database"]:
        config_dict["database"]["password"] = masked
    if "security" in config_dict and "jwt_secret_key" in config_dict["security"]:
        config_dict["security"]["jwt_secret_key"] = masked

    return config_dict
