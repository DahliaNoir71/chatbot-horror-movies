"""Tests unitaires pour TMDBExtractor (fichier fusionné)."""

from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.exceptions import RequestException

from src.etl.extractors.tmdb_extractor import TMDBExtractor, ExtractionState


class MockResponse:
    """Classe mock pour simuler les réponses de l'API TMDB."""

    def __init__(self, status_code: int, json_data: dict | None = None, text: str = "") -> None:
        """Initialise la réponse mockée."""
        self.status_code = status_code
        self.json_data = json_data or {}
        self.text = text
        self.headers = {"X-RateLimit-Remaining": "5"}

    def json(self) -> dict[str, Any]:
        """Retourne les données JSON simulées."""
        return self.json_data

    def raise_for_status(self) -> None:
        """Lève une exception si le statut est une erreur."""
        if 400 <= self.status_code < 600:
            raise requests.HTTPError(f"HTTP Error {self.status_code}")


@pytest.mark.unit
class TestTMDBExtractor:
    """Tests pour TMDBExtractor (fichier fusionné)."""

    @pytest.fixture(scope="function")
    def extractor(self) -> TMDBExtractor:
        """Extractor avec config de test."""
        return TMDBExtractor(
            config_overrides={
                "api_key": "test_key",
                "default_max_pages": 2,
                "use_period_batching": False,
                "include_adult": False,
                "horror_genre_id": 27,
                "base_url": "https://api.themoviedb.org/3"
            }
        )

    @pytest.fixture
    def mock_session(self, extractor: TMDBExtractor) -> MagicMock:
        """Remplace la session de l'extracteur par un mock."""
        mock = MagicMock()
        extractor.session = mock
        return mock

    @pytest.fixture
    def mock_tmdb_response(self) -> dict[str, Any]:
        """Retourne une réponse mockée de l'API TMDB."""
        return {
            "page": 1,
            "total_pages": 10,
            "total_results": 200,
            "results": [
                {"id": 1, "title": "Film 1", "release_date": "2020-01-01"},
                {"id": 2, "title": "Film 2", "release_date": "2020-01-02"},
            ]
        }

    # Tests d'initialisation

    @staticmethod
    def test_initialization(extractor: TMDBExtractor) -> None:
        """Test initialisation."""
        assert extractor.api_key == "test_key"
        assert extractor.base_url == "https://api.themoviedb.org/3"
        assert extractor.cfg.horror_genre_id == 27
        assert extractor.use_period_batching is False

    @staticmethod
    def test_missing_api_key_raises() -> None:
        """Test erreur si clé API manquante."""
        with pytest.raises(ValueError, match="TMDB_API_KEY manquante"):
            TMDBExtractor(config_overrides={"api_key": ""})

    # Tests de gestion des requêtes

    @staticmethod
    def test_make_request_success(
        extractor: TMDBExtractor, mock_session: MagicMock, mock_tmdb_response: dict[str, Any]
    ) -> None:
        """Test requête réussie."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "39"}
        mock_response.json.return_value = mock_tmdb_response
        mock_session.get.return_value = mock_response

        result = extractor._make_request("/test")

        assert result == mock_tmdb_response
        assert extractor.stats["total_requests"] == 1

    @staticmethod
    def test_make_request_handles_http_error(
        extractor: TMDBExtractor, mock_session: MagicMock
    ) -> None:
        """Test la gestion des erreurs HTTP."""
        mock_response = MockResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            json_data={"status_message": "Internal Server Error"},
        )
        mock_session.get.return_value = mock_response

        with pytest.raises(requests.RequestException) as exc_info:
            extractor._make_request("/test")

        assert "HTTP Error 500" in str(exc_info.value)
        assert extractor.stats["failed_requests"] == 1

    @staticmethod
    def test_make_request_handles_connection_error(
        extractor: TMDBExtractor, mock_session: MagicMock
    ) -> None:
        """Test la gestion des erreurs de connexion."""
        mock_session.get.side_effect = RequestException("Erreur de connexion")

        with pytest.raises(RequestException):
            extractor._make_request("/test")

        assert extractor.stats["failed_requests"] == 1

    # Tests de pagination

    @staticmethod
    def test_should_stop_extraction_conditions() -> None:
        """Test les conditions d'arrêt de l'extraction."""
        # Test max_pages atteint
        state = ExtractionState(
            all_movies=[], current_page=11, total_pages=20, max_pages=10
        )
        should_stop, reason = TMDBExtractor._should_stop_extraction(state)
        assert should_stop is True
        assert "Limite de 10 pages" in reason

        # Test total_pages atteint
        state = ExtractionState(
            all_movies=[], current_page=21, total_pages=20, max_pages=30
        )
        should_stop, reason = TMDBExtractor._should_stop_extraction(state)
        assert should_stop is True
        assert "Toutes les pages extraites (20 pages)" in reason

        # Test extraction non terminée
        state = ExtractionState(
            all_movies=[], current_page=5, total_pages=20, max_pages=30
        )
        should_stop, _ = TMDBExtractor._should_stop_extraction(state)
        assert should_stop is False

    @patch("src.etl.extractors.tmdb_extractor.TMDBExtractor._make_request")
    def test_fetch_page(
        self,
        mock_request: MagicMock,
        extractor: TMDBExtractor,
        mock_tmdb_response: dict[str, Any],
    ) -> None:
        """Test récupération page."""
        mock_request.return_value = mock_tmdb_response

        result = extractor._fetch_page(page=1)

        assert result == mock_tmdb_response
        mock_request.assert_called_once()
        call_args = mock_request.call_args[1]["params"]
        assert call_args["with_genres"] == 27
        assert call_args["page"] == 1

    # Tests de découverte de films

    @staticmethod
    def test_discover_horror_movies_standard_mode(
            extractor: TMDBExtractor
    ) -> None:
        """Test mode standard."""
        extractor.cfg.use_period_batching = False

        with patch.object(
                extractor, "_discover_standard", return_value=[{"id": 1}]
        ) as mock_discover:
            result = extractor.discover_horror_movies(max_pages=2)

            assert result == [{"id": 1}]
            mock_discover.assert_called_once_with(2)

    # Tests d'enrichissement

    @patch("src.etl.extractors.tmdb_extractor.TMDBExtractor._make_request")
    def test_enrich_movie_details(
        self, mock_request: MagicMock, extractor: TMDBExtractor
    ) -> None:
        """Test enrichissement détails."""
        movies_to_enrich = [{"id": 694, "title": "The Shining"}]
        mock_request.return_value = {
            "id": 694,
            "runtime": 146,
            "credits": {"cast": []},
        }

        enriched = extractor.enrich_movie_details(movies_to_enrich)

        assert len(enriched) == 1
        assert enriched[0]["runtime"] == 146
        assert "credits" in enriched[0]

