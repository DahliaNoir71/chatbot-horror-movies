"""Tests unitaires pour settings."""

import pytest
from pydantic import ValidationError

from src.settings import (
    TMDBSettings,
    DatabaseSettings,
    SecuritySettings,
    Settings,
    settings,
)


@pytest.fixture
def clean_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nettoie l'environnement pour les tests de settings."""
    # Suppression des variables d'environnement
    vars_to_clear = [
        "TMDB_API_KEY", "TMDB_BASE_URL", "TMDB_LANGUAGE", "TMDB_INCLUDE_ADULT",
        "TMDB_HORROR_GENRE_ID", "TMDB_YEAR_MIN", "TMDB_YEAR_MAX",
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER",
        "POSTGRES_PASSWORD", "DATABASE_URL",
        "JWT_SECRET_KEY", "JWT_ALGORITHM", "JWT_EXPIRE_MINUTES"
    ]
    for var in vars_to_clear:
        monkeypatch.delenv(var, raising=False)

    # Désactivation de la lecture du fichier .env
    classes_to_patch = [TMDBSettings, DatabaseSettings, SecuritySettings, Settings]
    for cls in classes_to_patch:
        new_config = cls.model_config.copy()
        new_config['env_file'] = None
        monkeypatch.setattr(cls, 'model_config', new_config)


@pytest.mark.unit
@pytest.mark.usefixtures("clean_settings_env")
class TestTMDBSettings:
    """Tests TMDBSettings."""

    @staticmethod
    def test_default_values() -> None:
        """Test valeurs par défaut."""
        tmdb = TMDBSettings(TMDB_API_KEY="test_key_12345")

        assert tmdb.base_url == "https://api.themoviedb.org/3"
        assert tmdb.language == "en-US"
        assert tmdb.horror_genre_id == 27
        assert tmdb.include_adult is False

    @staticmethod
    def test_missing_api_key_raises() -> None:
        """Test erreur si clé manquante."""
        with pytest.raises(ValidationError, match="TMDB_API_KEY"):
            TMDBSettings()

    @staticmethod
    def test_year_validation() -> None:
        """Test validation des années."""
        # Année minimale
        with pytest.raises(ValidationError, match="1888"):
            TMDBSettings(TMDB_API_KEY="test_key", TMDB_YEAR_MIN=1800)

        # Année maximale
        with pytest.raises(ValidationError, match="inférieur"):
            TMDBSettings(
                TMDB_API_KEY="test_key",
                TMDB_YEAR_MIN=2000,
                TMDB_YEAR_MAX=1999
            )


@pytest.mark.unit
@pytest.mark.usefixtures("clean_settings_env")
class TestDatabaseSettings:
    """Tests DatabaseSettings."""

    @staticmethod
    def test_default_connection_url() -> None:
        """Test génération URL par défaut."""
        db = DatabaseSettings(POSTGRES_PASSWORD="secret")
        expected = "postgresql://horrorbot_user:secret@localhost:5432/horrorbot"
        assert db.connection_url == expected

    @staticmethod
    def test_custom_connection_url() -> None:
        """Test URL custom prioritaire."""
        custom_url = "postgresql://custom:pass@host:5432/db"
        db = DatabaseSettings(DATABASE_URL=custom_url, POSTGRES_PASSWORD="ignored")
        assert db.connection_url == custom_url


@pytest.mark.unit
@pytest.mark.usefixtures("clean_settings_env")
class TestSecuritySettings:
    """Tests SecuritySettings."""

    @staticmethod
    def test_valid_jwt_secret() -> None:
        """Test secret valide."""
        secret = "a" * 32
        security = SecuritySettings(JWT_SECRET_KEY=secret)
        assert security.jwt_secret_key == secret
        assert security.jwt_algorithm == "HS256"


@pytest.mark.unit
@pytest.mark.usefixtures("clean_settings_env")
class TestGlobalSettings:
    """Tests Settings globaux."""

    @staticmethod
    def test_nested_settings_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialisation settings imbriqués."""
        # Création d'un dictionnaire avec les valeurs de test
        test_data = {
            "ENVIRONMENT": "test",
            "TMDB_API_KEY": "test_key_123456789012345678901234567890",
            "TMDB_BASE_URL": "https://api.themoviedb.org/3",
            "TMDB_IMAGE_BASE_URL": "https://image.tmdb.org/t/p/w500",
            "TMDB_LANGUAGE": "en-US",
            "TMDB_INCLUDE_ADULT": False,
            "TMDB_HORROR_GENRE_ID": 27,
            "TMDB_YEAR_MIN": 1960,
            "TMDB_YEAR_MAX": 2025,
            "TMDB_YEARS_PER_BATCH": 5,
            "TMDB_MAX_PAGES": 5,
            "POSTGRES_PASSWORD": "db_pass",
            "JWT_SECRET_KEY": "a" * 32,
            "JWT_ALGORITHM": "HS256",
            "RATE_LIMIT_PER_MINUTE": 100,
            "RATE_LIMIT_PER_HOUR": 1000
        }

        # Injection via variables d'environnement (comportement natif de BaseSettings)
        for key, value in test_data.items():
            monkeypatch.setenv(key, str(value))

        # Création de l'instance Settings avec les variables d'environnement
        config = Settings()

        # Vérifications
        assert config.tmdb.api_key == "test_key_123456789012345678901234567890"
        assert config.database.password == "db_pass"
        assert config.security.jwt_secret_key == "a" * 32
        assert config.environment == "test"
        assert config.database.connection_url is not None

    @staticmethod
    def test_settings_has_required_sections() -> None:
        """Test sections requises présentes."""
        required_sections = ["tmdb", "database", "security"]
        for section in required_sections:
            assert hasattr(settings, section), f"Section manquante: {section}"
