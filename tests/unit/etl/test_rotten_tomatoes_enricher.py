"""Tests unitaires pour RottenTomatoesEnricher."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import os

from src.etl.extractors.rotten_tomatoes_enricher import RottenTomatoesEnricher

@pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="Tests RT skippés en CI (nécessitent Playwright)"
)
@pytest.mark.unit
class TestRottenTomatoesEnricher:
    """Tests pour RottenTomatoesEnricher (fichier fusionné)."""

    @pytest.fixture
    def enricher(self) -> RottenTomatoesEnricher:
        """Enricher de test avec mock du logger."""
        with patch('src.etl.extractors.rotten_tomatoes_enricher.setup_logger'):
            return RottenTomatoesEnricher()

    @pytest.fixture
    def sample_tmdb_movie(self) -> dict[str, Any]:
        """Retourne un exemple de film TMDB pour les tests."""
        return {
            "id": 694,
            "title": "The Shining",
            "release_date": "1980-05-23",
            "original_language": "en"
        }

    @pytest.fixture
    def sample_tmdb_movies(self) -> list[dict[str, Any]]:
        """Retourne une liste d'exemples de films TMDB pour les tests."""
        return [
            {"id": 694, "title": "The Shining", "release_date": "1980-05-23"},
            {"id": 807, "title": "Alien", "release_date": "1979-05-25"},
            {"id": 1091, "title": "The Thing", "release_date": "1982-06-25"}
        ]

    @pytest.fixture
    def sample_rt_data(self) -> dict[str, Any]:
        """Retourne des exemples de données Rotten Tomatoes pour les tests."""
        return {
            "tomatometer_score": 85,
            "audience_score": 93,
            "critics_consensus": "A modern horror classic.",
            "certified_fresh": True,
            "critics_count": 120
        }

    @pytest.fixture
    def mock_async_crawler(self) -> AsyncMock:
        """Retourne un mock de crawler asynchrone pour les tests."""
        return AsyncMock()

    # Tests de base

    @staticmethod
    def test_build_film_url_success() -> None:
        """Test construction URL succès."""
        url = RottenTomatoesEnricher._build_film_url("The Shining")
        assert url == "/m/the_shining"

    @staticmethod
    def test_build_film_url_special_chars() -> None:
        """Test translittération caractères spéciaux."""
        url = RottenTomatoesEnricher._build_film_url("Amélie")
        assert url == "/m/amelie"

    # Tests d'extraction de détails

    @staticmethod
    async def test_extract_film_details_missing_scores(
            enricher: RottenTomatoesEnricher, mock_async_crawler: AsyncMock
    ) -> None:
        """Test d'extraction avec données de score manquantes."""
        # Création d'un mock de réponse avec un format JSON valide mais sans scores
        mock_response = {
            "scoreboard": {
                "tomatometerScore": {}
            },
            "criticsScore": {},
            "audienceScore": {}
        }

        html = f"""
        <html>
            <script id="media-scorecard-json" type="application/json">
                {json.dumps(mock_response)}
            </script>
        </html>
        """

        # Configuration du mock pour retourner une réponse réussie avec le HTML simulé
        mock_async_crawler.arun.return_value.success = True
        mock_async_crawler.arun.return_value.html = html

        # Désactive temporairement les retries pour ce test
        with patch('tenacity.retry_if_not_result', return_value=lambda _: False):
            details = await enricher._extract_film_details(mock_async_crawler, "/m/test")

        # Vérifie que les champs de score ne sont pas présents
        # car les dictionnaires de scores étaient vides
        assert "tomatometer_score" not in details
        assert "audience_score" not in details
        # Vérifie que l'URL a bien été ajoutée
        assert details["rotten_tomatoes_url"] == "https://www.rottentomatoes.com/m/test"

    # Tests de recherche de films

    @staticmethod
    async def test_check_film_url_exists(
            enricher: RottenTomatoesEnricher, mock_async_crawler: AsyncMock
    ) -> None:
        """Test vérification URL existante."""
        mock_async_crawler.arun.return_value.success = True
        mock_async_crawler.arun.return_value.html = "a" * 15000

        exists = await enricher._check_film_url(
            mock_async_crawler, "/m/shining", "The Shining"
        )

        assert exists is True

    @staticmethod
    async def test_search_film_title_found(
            enricher: RottenTomatoesEnricher, mock_async_crawler: AsyncMock
    ) -> None:
        """Test recherche succès titre."""
        with patch.object(
                enricher, "_check_film_url", return_value=True
        ) as mock_check:
            url = await enricher._search_film(
                mock_async_crawler, "The Shining", "The Shining"
            )

            assert url == "/m/the_shining"
            mock_check.assert_called_once()

    # Tests d'extraction de scores

    @staticmethod
    def test_extract_critics_scores(sample_rt_data: dict[str, Any]) -> None:
        """Test extraction scores critiques."""
        scorecard = {
            "criticsScore": {
                "score": 85,
                "certified": True,
                "reviewCount": 89,
                "averageRating": 8.4,
            }
        }
        details: dict[str, Any] = {}

        RottenTomatoesEnricher._extract_critics_scores(scorecard, details)

        assert details["tomatometer_score"] == 85
        assert details["certified_fresh"] is True
        assert details["critics_count"] == 89

    # Tests d'enrichissement

    @staticmethod
    async def test_enrich_film_success(
            enricher: RottenTomatoesEnricher,
            mock_async_crawler: AsyncMock,
            sample_tmdb_movie: dict[str, Any],
            sample_rt_data: dict[str, Any]
    ) -> None:
        """Test enrichissement succès."""
        # S'assurer que processed_films est vide
        enricher.processed_films.clear()

        with patch.object(enricher, "_search_film", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "/m/shining"
            with patch.object(enricher, "_extract_film_details", new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = sample_rt_data
                with patch.object(enricher, "_save_checkpoint"):
                    result = await enricher.enrich_film(mock_async_crawler, sample_tmdb_movie)
                    print(result)

                    assert result is not None
                    assert result["audience_score"] == 93
                    assert result["tomatometer_score"] == sample_rt_data["tomatometer_score"]
                    assert result["title"] == sample_tmdb_movie["title"]

    @staticmethod
    async def test_enrich_film_not_found(
            enricher: RottenTomatoesEnricher,
            mock_async_crawler: AsyncMock,
            sample_tmdb_movie: dict[str, Any]
    ) -> None:
        """Test film non trouvé."""
        with patch.object(enricher, "_search_film", return_value=None):
            result = await enricher.enrich_film(mock_async_crawler, sample_tmdb_movie)

            # Vérifie que le film retourné est le même que celui en entrée
            # (comportement actuel de la méthode enrich_film)
            assert result == sample_tmdb_movie

    @staticmethod
    async def test_enrich_films_async_batch(
            enricher: RottenTomatoesEnricher,
            sample_tmdb_movies: list[dict[str, Any]]
    ) -> None:
        """Test enrichissement batch."""
        mock_crawler = AsyncMock()

        # Mock AsyncWebCrawler au niveau module pour éviter lancement navigateur
        with patch(
                "src.etl.extractors.rotten_tomatoes_enricher.AsyncWebCrawler"
        ) as MockCrawler:
            # Configure le context manager async
            MockCrawler.return_value.__aenter__.return_value = mock_crawler
            MockCrawler.return_value.__aexit__.return_value = None

            with patch.object(
                    enricher,
                    "enrich_film",
                    new_callable=AsyncMock,
                    # Retourne le film tel quel
                    side_effect=lambda crawler, film: film
            ):
                results = await enricher.enrich_films_async(
                    sample_tmdb_movies[:3],
                    max_concurrent=2
                )

        assert len(results) == 3
        # Vérifie que tous les films sont retournés
        assert results[0]["title"] == "The Shining"
        assert results[1]["title"] == "Alien"
        assert results[2]["title"] == "The Thing"
