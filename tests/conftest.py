"""Fixtures pytest partagées pour tests ETL."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, AsyncMock

import pytest
from httpx import Response

from src.settings import settings


@pytest.fixture(autouse=True, scope="function")
def mock_env_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock variables env pour tests reproductibles."""
    # TMDB settings
    monkeypatch.setenv("TMDB_API_KEY", "test_api_key_12345678901234567890")
    monkeypatch.setenv("TMDB_BASE_URL", "https://api.themoviedb.org/3")
    monkeypatch.setenv("TMDB_LANGUAGE", "en-US")
    monkeypatch.setenv("TMDB_INCLUDE_ADULT", "false")
    monkeypatch.setenv("TMDB_HORROR_GENRE_ID", "27")
    monkeypatch.setenv("TMDB_YEAR_MIN", "1960")
    monkeypatch.setenv("TMDB_YEAR_MAX", "2024")
    monkeypatch.setenv("TMDB_YEARS_PER_BATCH", "5")
    monkeypatch.setenv("TMDB_USE_PERIOD_BATCHING", "false")
    monkeypatch.setenv("TMDB_MAX_PAGES", "5")

    # Security settings
    monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_secret_key_12345678901234567890")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "30")

    # Database settings
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "test_horrorbot")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    # CORS settings
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")

    # Environment
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


@pytest.fixture(autouse=True, scope="function")
def reset_settings_cache() -> None:
    """Force rechargement settings entre tests."""
    # Pydantic Settings cache les valeurs, on doit les clear
    from src.settings import TMDBSettings, SecuritySettings

    # Clear caches Pydantic
    TMDBSettings.model_config["validate_assignment"] = True
    SecuritySettings.model_config["validate_assignment"] = True


@pytest.fixture
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Répertoire temporaire pour données de test."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "checkpoints").mkdir()
    (data_dir / "raw").mkdir()
    (data_dir / "processed").mkdir()
    (data_dir / "logs").mkdir()

    # Override settings paths
    monkeypatch.setattr(settings.paths, "checkpoints_dir", data_dir / "checkpoints")
    monkeypatch.setattr(settings.paths, "raw_dir", data_dir / "raw")
    monkeypatch.setattr(settings.paths, "processed_dir", data_dir / "processed")
    monkeypatch.setattr(settings.paths, "logs_dir", data_dir / "logs")

    return data_dir


@pytest.fixture
def sample_tmdb_movie() -> dict[str, Any]:
    """Film TMDB factice."""
    return {
        "id": 694,
        "title": "The Shining",
        "original_title": "The Shining",
        "overview": "Jack Torrance becomes winter caretaker...",
        "release_date": "1980-05-23",
        "vote_average": 8.2,
        "vote_count": 15234,
        "popularity": 87.5,
        "poster_path": "/b6ko0IKC8MdYBBPkkA1aBPLe2yz.jpg",
        "backdrop_path": "/tWjZI4q8g6VHg36qIXJ3KXg7p6K.jpg",
        "genre_ids": [27, 53],
        "adult": False,
        "video": False,
        "original_language": "en",
        "imdb_id": "tt0081505",
    }


@pytest.fixture
def sample_tmdb_movies(sample_tmdb_movie: dict[str, Any]) -> list[dict[str, Any]]:
    """Liste de films TMDB factices."""
    movies = []
    for i in range(5):
        movie = sample_tmdb_movie.copy()
        movie["id"] = 694 + i
        movie["title"] = f"Horror Film {i + 1}"
        movies.append(movie)
    return movies


@pytest.fixture
def sample_rt_data() -> dict[str, Any]:
    """Données Rotten Tomatoes factices."""
    return {
        "tomatometer_score": 85,
        "audience_score": 93,
        "certified_fresh": True,
        "critics_count": 89,
        "audience_count": 250000,
        "critics_consensus": "Though it deviates from Stephen King's novel, Stanley Kubrick's The Shining is a chilling"
                             " masterclass.",
        "rotten_tomatoes_url": "https://www.rottentomatoes.com/m/shining",
    }


@pytest.fixture
def mock_tmdb_response(sample_tmdb_movies: list[dict[str, Any]]) -> dict[str, Any]:
    """Réponse API TMDB factice."""
    return {
        "page": 1,
        "total_pages": 10,
        "total_results": 200,
        "results": sample_tmdb_movies,
    }


@pytest.fixture
def mock_rt_html() -> str:
    """HTML Rotten Tomatoes factice."""
    return """
    <html>
        <script id="media-scorecard-json">
        {
            "criticsScore": {
                "score": 85,
                "certified": true,
                "reviewCount": 89,
                "averageRating": 8.4
            },
            "audienceScore": {
                "score": 93,
                "reviewCount": 250000,
                "averageRating": 4.6
            }
        }
        </script>
        <div id="critics-consensus">
            <p>Though it deviates from Stephen King's novel, Stanley Kubrick's The Shining is a chilling masterclass.
            </p>
        </div>
    </html>
    """


@pytest.fixture
def mock_httpx_client() -> MagicMock:
    """Client HTTP mocké pour requests."""
    client = MagicMock()

    def get_side_effect(url: str, **kwargs: dict[str, Any]) -> MagicMock:
        """
        Mocked side effect for `client.get` method.

        Args:
            url: URL of the request
            **kwargs: Additional keyword arguments for the request

        Returns:
            A mocked `Response` object with a status code of 200 and
            a JSON response that depends on the URL.
        """
        response = MagicMock(spec=Response)
        response.status_code = 200
        response.headers = {"X-RateLimit-Remaining": "39"}

        if "/discover/movie" in url:
            response.json.return_value = {
                "page": 1,
                "total_pages": 5,
                "total_results": 100,
                "results": [{"id": i, "title": f"Film {i}"} for i in range(20)],
            }
        elif "/movie/" in url:
            response.json.return_value = {
                "id": 694,
                "title": "Test Movie",
                "credits": {"cast": [], "crew": []},
                "keywords": {"keywords": []},
            }

        return response

    client.get.side_effect = get_side_effect
    return client


@pytest.fixture
def mock_crawler_result() -> MagicMock:
    """Résultat Crawl4AI mocké."""
    result = MagicMock()
    result.success = True
    result.html = """
    <script id="media-scorecard-json">
    {"criticsScore": {"score": 85}}
    </script>
    """
    return result


@pytest.fixture
async def mock_async_crawler(mock_crawler_result: MagicMock) -> AsyncMock:
    """AsyncWebCrawler mocké."""
    crawler = AsyncMock()
    crawler.arun = AsyncMock(return_value=mock_crawler_result)
    return crawler


@pytest.fixture
def checkpoint_file(tmp_data_dir: Path) -> Path:
    """Fichier checkpoint factice."""
    checkpoint_path = tmp_data_dir / "checkpoints" / "test_checkpoint.json"
    checkpoint_data = {
        "timestamp": datetime.now().isoformat(),
        "data": {"movies": [{"id": 1, "title": "Test"}], "last_page": 1},
    }

    checkpoint_path.write_text(json.dumps(checkpoint_data), encoding="utf-8")
    return checkpoint_path


@pytest.fixture(autouse=True)
def override_settings(tmp_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Override settings pour utiliser répertoires temporaires."""
    monkeypatch.setattr(settings.paths, "checkpoints_dir", tmp_data_dir / "checkpoints")
    monkeypatch.setattr(settings.paths, "raw_dir", tmp_data_dir / "raw")
    monkeypatch.setattr(settings.paths, "processed_dir", tmp_data_dir / "processed")
    monkeypatch.setattr(settings.paths, "logs_dir", tmp_data_dir / "logs")

