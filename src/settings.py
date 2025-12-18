"""Configuration centralisée du projet HorrorBot avec Pydantic Settings."""

from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Trouve le .env à la racine du projet
_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)
    print(f"✅ Configuration chargée depuis {_ENV_FILE}")
else:
    print("⚠️ Pas de .env trouvé, utilisation des variables d'environnement")

load_dotenv(_ENV_FILE)

from pydantic import Field, field_validator  # noqa: E402
from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: E402

# ============================================================================
# SETTINGS CHEMINS ET LOGGING
# ============================================================================


class PathsSettings(BaseSettings):
    """Configuration des chemins de données et logs."""

    _project_root: Path = _PROJECT_ROOT

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def data_dir(self) -> Path:
        """Répertoire racine des données."""
        return self._project_root / "data"

    @property
    def raw_dir(self) -> Path:
        """Données brutes (CSV, JSON sources)."""
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        """Données finales agrégées."""
        return self.data_dir / "processed"

    @property
    def checkpoints_dir(self) -> Path:
        """Checkpoints ETL et pipeline."""
        return self.data_dir / "checkpoints"

    @property
    def imports_dir(self) -> Path:
        """Fichiers temporaires d'import DB."""
        return self.data_dir / "imports"

    @property
    def logs_dir(self) -> Path:
        """Logs applicatifs."""
        return self._project_root / "logs"

    def model_post_init(self, _: object) -> None:
        """Crée automatiquement tous les répertoires nécessaires."""
        directories = [
            self.data_dir,
            self.raw_dir,
            self.processed_dir,
            self.checkpoints_dir,
            self.imports_dir,
            self.logs_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


class LoggingSettings(BaseSettings):
    """Configuration logs."""

    level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: Path = Field(default=Path("logs"), alias="LOG_DIR")
    format: str = Field(default="json", alias="LOG_FORMAT")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Valide le niveau de log."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL invalide. Valeurs: {valid_levels}")
        return v_upper


class ETLSettings(BaseSettings):
    """Configuration pipeline ETL."""

    max_workers: int = Field(default=4, alias="ETL_MAX_WORKERS")
    scraping_delay: float = Field(default=2.0, alias="SCRAPING_DELAY")
    user_agent: str = Field(default="HorrorBot-ETL/1.0 (Educational Project)", alias="USER_AGENT")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# ============================================================================
# SOURCE 1 : TMDB (API REST)
# ============================================================================


class TMDBSettings(BaseSettings):
    """Configuration API TMDB."""

    api_key: str = Field(default="", alias="TMDB_API_KEY")
    base_url: str = Field(default="https://api.themoviedb.org/3", alias="TMDB_BASE_URL")
    image_base_url: str = Field(
        default="https://image.tmdb.org/t/p/w500", alias="TMDB_IMAGE_BASE_URL"
    )

    # Paramètres d'extraction
    language: str = Field(default="en-US", alias="TMDB_LANGUAGE")
    include_adult: bool = Field(default=False, alias="TMDB_INCLUDE_ADULT")
    horror_genre_id: int = Field(default=27, alias="TMDB_HORROR_GENRE_ID")

    # Filtres temporels
    year_min: int = Field(default=1960, alias="TMDB_YEAR_MIN")
    year_max: int = Field(default=datetime.now().year, alias="TMDB_YEAR_MAX")
    years_per_batch: int = Field(default=5, alias="TMDB_YEARS_PER_BATCH")

    # Rate limiting
    requests_per_period: int = 40
    period_seconds: int = 10
    min_request_delay: float = 0.25
    use_period_batching: bool = Field(default=False, alias="TMDB_USE_PERIOD_BATCHING")

    # Extraction
    default_max_pages: int = Field(default=5, alias="TMDB_MAX_PAGES")
    checkpoint_save_interval: int = 10
    enrich_movies: bool = False
    save_checkpoints: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_configured(self) -> bool:
        """Check if TMDB API key is configured."""
        return bool(self.api_key and self.api_key != "your_api_key_here")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Valide que la clé API est définie."""
        if not v or v == "your_api_key_here":
            raise ValueError(
                "TMDB_API_KEY invalide. Obtenir une clé sur https://www.themoviedb.org/settings/api"
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
            raise ValueError(f"TMDB_YEAR_MIN ne peut pas être dans le futur ({current_year})")
        return v

    @field_validator("year_max")
    @classmethod
    def validate_year_max(cls, v: int, values: dict[str, Any]) -> int:
        """Valide que l'année maximale est plausible."""
        current_year = datetime.now().year
        year_min = values.data.get("year_min", 1900)

        if v < year_min:
            raise ValueError(f"TMDB_YEAR_MAX ({v}) < TMDB_YEAR_MIN ({year_min})")
        if v > current_year:
            raise ValueError("TMDB_YEAR_MAX ne peut pas être dans le futur")
        return v

    @field_validator("years_per_batch")
    @classmethod
    def validate_years_per_batch(cls, v: int) -> int:
        """Valide que years_per_batch est raisonnable."""
        if not 1 <= v <= 10:
            raise ValueError("TMDB_YEARS_PER_BATCH doit être entre 1 et 10")
        return v


# ============================================================================
# SOURCE 2 : SPOTIFY (API REST OAuth2)
# ============================================================================


class SpotifySettings(BaseSettings):
    """Configuration API Spotify (OAuth2 Client Credentials)."""

    client_id: str = Field(default="", alias="SPOTIFY_CLIENT_ID")
    client_secret: str = Field(default="", alias="SPOTIFY_CLIENT_SECRET")
    auth_url: str = Field(
        default="https://accounts.spotify.com/api/token",
        alias="SPOTIFY_AUTH_URL",
    )
    api_base_url: str = Field(
        default="https://api.spotify.com/v1",
        alias="SPOTIFY_API_BASE_URL",
    )

    # Podcasts horror FR individuels
    podcast_jumpscare: str = Field(default="", alias="SPOTIFY_PODCAST_JUMPSCARE")
    podcast_monstersquad: str = Field(default="", alias="SPOTIFY_PODCAST_MONSTERSQUAD")
    podcast_shadowzcast: str = Field(default="", alias="SPOTIFY_PODCAST_SHADOWZCAST")

    # Rate limiting
    rate_limit_delay: float = Field(default=1.0, alias="SPOTIFY_RATE_LIMIT_DELAY")
    max_episodes_per_podcast: int = Field(default=50, alias="SPOTIFY_MAX_EPISODES")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_configured(self) -> bool:
        """Check if Spotify credentials are configured."""
        return bool(self.client_id and self.client_secret)

    @property
    def requests_per_second(self) -> float:
        """Requests per second (inverse of rate_limit_delay)."""
        return 1.0 / self.rate_limit_delay if self.rate_limit_delay > 0 else 1.0

    @property
    def podcast_ids(self) -> dict[str, str]:
        """Return dict of podcast name -> Spotify ID."""
        podcasts = {}
        if self.podcast_jumpscare:
            podcasts["JUMPSCARE"] = self.podcast_jumpscare
        if self.podcast_monstersquad:
            podcasts["Monster Squad"] = self.podcast_monstersquad
        if self.podcast_shadowzcast:
            podcasts["ShadowzCast"] = self.podcast_shadowzcast
        return podcasts


# ============================================================================
# SOURCE 3 : YOUTUBE (API REST)
# ============================================================================


class YouTubeSettings(BaseSettings):
    """Configuration YouTube Data API v3."""

    api_key: str = Field(default="", alias="YOUTUBE_API_KEY")
    api_base_url: str = Field(
        default="https://www.googleapis.com/youtube/v3",
        alias="YOUTUBE_API_BASE_URL",
    )

    # Channels horror FR (handles séparés par virgule)
    channel_handles_raw: str = Field(
        default="@Monstresdefilms",
        alias="YOUTUBE_CHANNEL_HANDLES",
    )

    # Rate limiting & quotas
    rate_limit_delay: float = Field(default=2.0, alias="YOUTUBE_RATE_LIMIT_DELAY")
    daily_quota_limit: int = Field(default=10000, alias="YOUTUBE_DAILY_QUOTA")
    max_results_per_page: int = Field(default=50, alias="YOUTUBE_MAX_RESULTS")
    max_videos_per_channel: int = Field(default=50, alias="YOUTUBE_MAX_VIDEOS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_configured(self) -> bool:
        """Check if YouTube API key is configured."""
        return bool(self.api_key)

    @property
    def requests_per_second(self) -> float:
        """Requests per second (inverse of rate_limit_delay)."""
        return 1.0 / self.rate_limit_delay if self.rate_limit_delay > 0 else 0.5

    @property
    def channel_handles(self) -> list[str]:
        """Parse channel handles from comma-separated string."""
        return [h.strip() for h in self.channel_handles_raw.split(",") if h.strip()]


# ============================================================================
# SOURCE 4 : KAGGLE (FICHIER CSV)
# ============================================================================


class KaggleSettings(BaseSettings):
    """Configuration Kaggle API pour téléchargement datasets."""

    username: str = Field(default="", alias="KAGGLE_USERNAME")
    key: str = Field(default="", alias="KAGGLE_KEY")

    # Dataset horror movies
    dataset_slug: str = Field(
        default="evangower/horror-movies",
        alias="KAGGLE_DATASET_SLUG",
    )

    # Filtres données
    min_vote_count: int = Field(default=10, alias="KAGGLE_MIN_VOTE_COUNT")
    min_year: int = Field(default=1960, alias="KAGGLE_MIN_YEAR")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_configured(self) -> bool:
        """Check if Kaggle credentials are configured."""
        return bool(self.username and self.key)


# ============================================================================
# SOURCE 5 : POSTGRESQL IMDB (BDD EXTERNE)
# ============================================================================


class ImdbDBSettings(BaseSettings):
    """Configuration PostgreSQL externe IMDB (port 5433)."""

    host: str = Field(default="localhost", alias="IMDB_DB_HOST")
    port: int = Field(default=5433, alias="IMDB_DB_PORT")
    database: str = Field(default="horror_imdb", alias="IMDB_DB_NAME")
    user: str = Field(default="imdb_user", alias="IMDB_DB_USER")
    password: str = Field(default="", alias="IMDB_DB_PASSWORD")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_configured(self) -> bool:
        """Check if IMDB DB credentials are configured."""
        return bool(self.password)

    @property
    def connection_url(self) -> str:
        """Generate PostgreSQL connection URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


# ============================================================================
# BASE DE DONNÉES PRINCIPALE HORRORBOT
# ============================================================================


class DatabaseSettings(BaseSettings):
    """Configuration PostgreSQL principale HorrorBot."""

    host: str = Field(default="localhost", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    database: str = Field(default="horrorbot", alias="POSTGRES_DB")
    user: str = Field(default="horrorbot_user", alias="POSTGRES_USER")
    password: str = Field(default="", alias="POSTGRES_PASSWORD")
    url: str | None = Field(default=None, alias="DATABASE_URL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_configured(self) -> bool:
        """Check if database credentials are configured."""
        return bool(self.password or self.url)

    @property
    def connection_url(self) -> str:
        """Génère l'URL de connexion PostgreSQL."""
        if self.url:
            return self.url
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


# ============================================================================
# SETTINGS E3 - API REST (FUTUR)
# ============================================================================


class APISettings(BaseSettings):
    """Configuration FastAPI (E3)."""

    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT")
    reload: bool = Field(default=True, alias="API_RELOAD")
    workers: int = Field(default=4, alias="API_WORKERS")
    public_url: str = Field(default="http://localhost:8000", alias="API_PUBLIC_URL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class SecuritySettings(BaseSettings):
    """Configuration JWT et rate limiting (E3)."""

    jwt_secret_key: str = Field(
        default="test_jwt_secret_not_for_production_minimum_32_chars_long",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, alias="JWT_EXPIRE_MINUTES")
    rate_limit_per_minute: int = Field(default=100, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, alias="RATE_LIMIT_PER_HOUR")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class CORSSettings(BaseSettings):
    """Configuration CORS (E3)."""

    origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def origins(self) -> list[str]:
        """Parse et retourne la liste des origines."""
        return [origin.strip() for origin in self.origins_raw.split(",")]


# ============================================================================
# CONFIGURATION GLOBALE
# ============================================================================


class Settings(BaseSettings):
    """Configuration globale de l'application."""

    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Chemins et logging
    paths: PathsSettings = Field(default_factory=PathsSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    etl: ETLSettings = Field(default_factory=ETLSettings)

    # Sources E1 - Extraction
    tmdb: TMDBSettings = Field(default_factory=TMDBSettings)
    spotify: SpotifySettings = Field(default_factory=SpotifySettings)
    youtube: YouTubeSettings = Field(default_factory=YouTubeSettings)
    kaggle: KaggleSettings = Field(default_factory=KaggleSettings)
    imdb_db: ImdbDBSettings = Field(default_factory=ImdbDBSettings)

    # Base principale
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    # E3 - API REST
    api: APISettings = Field(default_factory=APISettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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


# ============================================================================
# SINGLETON
# ============================================================================

settings = Settings()


# ============================================================================
# UTILITAIRES DEBUG
# ============================================================================


def print_settings() -> dict[str, Any]:
    """Affiche la configuration (sans secrets) pour debug."""
    config_dict = settings.model_dump()
    masked = "***MASKED***"

    # Masquer les secrets
    secrets_paths = [
        ("tmdb", "api_key"),
        ("spotify", "client_secret"),
        ("youtube", "api_key"),
        ("kaggle", "key"),
        ("imdb_db", "password"),
        ("database", "password"),
        ("security", "jwt_secret_key"),
    ]

    for section, key in secrets_paths:
        if section in config_dict and key in config_dict[section] and config_dict[section][key]:
            config_dict[section][key] = masked

    return config_dict


def print_sources_status() -> None:
    """Affiche le statut de configuration des sources E1."""
    sources = [
        ("TMDB", settings.tmdb.is_configured),
        ("Spotify", settings.spotify.is_configured),
        ("YouTube", settings.youtube.is_configured),
        ("Kaggle", settings.kaggle.is_configured),
        ("IMDB DB", settings.imdb_db.is_configured),
        ("Database", settings.database.is_configured),
    ]

    print("\n📊 STATUT SOURCES E1:")
    print("-" * 40)
    for name, configured in sources:
        status = "✅" if configured else "❌"
        print(f"  {status} {name}")
    print("-" * 40)
