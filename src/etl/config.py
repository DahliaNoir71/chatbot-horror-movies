"""
Configuration centralisée pour le projet HorrorBot.
Charge les variables d'environnement depuis .env
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Charger les variables depuis .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Config:
    """Configuration globale de l'application"""

    # -------------------------------------------------------------------------
    # Environnement
    # -------------------------------------------------------------------------
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # -------------------------------------------------------------------------
    # TMDB API
    # -------------------------------------------------------------------------
    TMDB_API_KEY: str = os.getenv("TMDB_API_KEY", "")
    TMDB_BASE_URL: str = os.getenv("TMDB_BASE_URL", "https://api.themoviedb.org/3")
    TMDB_IMAGE_BASE_URL: str = os.getenv(
        "TMDB_IMAGE_BASE_URL", "https://image.tmdb.org/t/p/w500"
    )

    # -------------------------------------------------------------------------
    # PostgreSQL - Base principale HorrorBot
    # -------------------------------------------------------------------------
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "horrorbot")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "horrorbot_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")

    @property
    def database_url(self) -> str:
        """URL de connexion PostgreSQL"""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # -------------------------------------------------------------------------
    # PostgreSQL - Base IMDb externe (extraction)
    # -------------------------------------------------------------------------
    IMDB_POSTGRES_HOST: str = os.getenv("IMDB_POSTGRES_HOST", "localhost")
    IMDB_POSTGRES_PORT: int = int(os.getenv("IMDB_POSTGRES_PORT", "5433"))
    IMDB_POSTGRES_DB: str = os.getenv("IMDB_POSTGRES_DB", "imdb_subset")
    IMDB_POSTGRES_USER: str = os.getenv("IMDB_POSTGRES_USER", "imdb_reader")
    IMDB_POSTGRES_PASSWORD: str = os.getenv("IMDB_POSTGRES_PASSWORD", "")

    @property
    def imdb_database_url(self) -> str:
        """URL de connexion PostgreSQL IMDb"""
        return (
            f"postgresql://{self.IMDB_POSTGRES_USER}:{self.IMDB_POSTGRES_PASSWORD}"
            f"@{self.IMDB_POSTGRES_HOST}:{self.IMDB_POSTGRES_PORT}/{self.IMDB_POSTGRES_DB}"
        )

    # -------------------------------------------------------------------------
    # Apache Spark
    # -------------------------------------------------------------------------
    SPARK_HOME: str = os.getenv("SPARK_HOME", "/opt/spark")
    SPARK_MASTER: str = os.getenv("SPARK_MASTER", "local[4]")
    SPARK_DRIVER_MEMORY: str = os.getenv("SPARK_DRIVER_MEMORY", "4g")
    SPARK_EXECUTOR_MEMORY: str = os.getenv("SPARK_EXECUTOR_MEMORY", "4g")
    SPARK_PARQUET_PATH: str = os.getenv(
        "SPARK_PARQUET_PATH", "data/big_data/movies_large.parquet"
    )

    # -------------------------------------------------------------------------
    # API REST
    # -------------------------------------------------------------------------
    # Default to localhost in development for security
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_RELOAD: bool = os.getenv("API_RELOAD", "true").lower() == "true"
    API_WORKERS: int = int(os.getenv("API_WORKERS", "4"))
    API_PUBLIC_URL: str = os.getenv("API_PUBLIC_URL", "http://localhost:8000")

    # -------------------------------------------------------------------------
    # Sécurité - JWT
    # -------------------------------------------------------------------------
    # JWT secret key (must be set via environment variable)
    JWT_SECRET_KEY: str = os.environ["JWT_SECRET_KEY"]
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))

    # -------------------------------------------------------------------------
    # Sécurité - Rate Limiting
    # -------------------------------------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
    RATE_LIMIT_PER_HOUR: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    @property
    def cors_origins(self) -> list[str]:
        """Liste des origines CORS autorisées"""
        origins_str = os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:8000"
        )
        return [origin.strip() for origin in origins_str.split(",")]

    # -------------------------------------------------------------------------
    # ETL - Répertoires
    # -------------------------------------------------------------------------
    DATA_RAW_DIR: str = os.getenv("DATA_RAW_DIR", "data/raw")
    DATA_PROCESSED_DIR: str = os.getenv("DATA_PROCESSED_DIR", "data/processed")
    DATA_CHECKPOINTS_DIR: str = os.getenv("DATA_CHECKPOINTS_DIR", "data/checkpoints")

    @property
    def raw_dir(self) -> Path:
        """Chemin absolu vers data/raw"""
        path = Path(self.DATA_RAW_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def processed_dir(self) -> Path:
        """Chemin absolu vers data/processed"""
        path = Path(self.DATA_PROCESSED_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def checkpoints_dir(self) -> Path:
        """Chemin absolu vers data/checkpoints"""
        path = Path(self.DATA_CHECKPOINTS_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # -------------------------------------------------------------------------
    # ETL - Configuration
    # -------------------------------------------------------------------------
    ETL_MAX_WORKERS: int = int(os.getenv("ETL_MAX_WORKERS", "4"))
    SCRAPING_DELAY: float = float(os.getenv("SCRAPING_DELAY", "2.0"))
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "HorrorBot-ETL/1.0 (Educational Project)",
    )

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")

    @property
    def logs_dir(self) -> Path:
        """Chemin absolu vers logs/"""
        path = Path(self.LOG_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    def validate(self) -> None:
        """Valide que toutes les variables critiques sont définies"""
        errors = []

        if not self.TMDB_API_KEY:
            errors.append(
                "TMDB_API_KEY manquante. "
                "Obtenir une clé sur https://www.themoviedb.org/settings/api"
            )

        # JWT_SECRET_KEY is already required to be set via environment variable
        # Just validate it's not empty
        if not self.JWT_SECRET_KEY:
            errors.append(
                "JWT_SECRET_KEY non définie. Définir avec : export JWT_SECRET_KEY=$(openssl rand -hex 32)"
            )

        if not self.POSTGRES_PASSWORD:
            errors.append("POSTGRES_PASSWORD manquante dans .env")

        if errors and self.ENVIRONMENT == "production":
            raise ValueError(
                "Configuration invalide :\n" + "\n".join(f"- {e}" for e in errors)
            )

        if errors and self.ENVIRONMENT == "development":
            print(
                "⚠️  Avertissements configuration :\n"
                + "\n".join(f"- {e}" for e in errors)
            )


# Instance globale de configuration
config = Config()

# Valider la configuration au chargement
config.validate()
