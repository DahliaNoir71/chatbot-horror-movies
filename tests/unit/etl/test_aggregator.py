"""Tests unitaires pour DataAggregator."""

import pytest
from typing import Any
from src.etl.aggregator import DataAggregator, MovieSchema


@pytest.mark.unit
class TestDataAggregator:
    """Tests DataAggregator."""

    @pytest.fixture
    def aggregator(self) -> DataAggregator:
        """Aggregator de test."""
        return DataAggregator()

    @staticmethod
    def test_merge_sources_tmdb_only(
        aggregator: DataAggregator, sample_tmdb_movie: dict[str, Any]
    ) -> None:
        """Test fusion TMDB seul."""
        merged = aggregator.merge_sources(sample_tmdb_movie, None)

        assert merged["tmdb_id"] == 694
        assert merged["title"] == "The Shining"
        assert "tomatometer_score" not in merged

    @staticmethod
    def test_merge_sources_with_rt(
        aggregator: DataAggregator,
        sample_tmdb_movie: dict[str, Any],
        sample_rt_data: dict[str, Any]
    ) -> None:
        """Test fusion TMDB + RT."""
        merged = aggregator.merge_sources(sample_tmdb_movie, sample_rt_data)

        assert merged["tmdb_id"] == 694
        assert merged["tomatometer_score"] == 85
        assert merged["critics_consensus"] == sample_rt_data["critics_consensus"]

    @staticmethod
    def test_validate_movie_success(aggregator: DataAggregator) -> None:
        """Test validation succès."""
        movie = {
            "tmdb_id": 694,
            "title": "The Shining",
            "year": 1980,
            "release_date": "1980-05-23",
            "original_language": "en",
            "vote_average": 8.2,
            "vote_count": 1000,
            "popularity": 50.0,
        }

        validated = aggregator.validate_movie(movie)

        assert validated is not None
        assert isinstance(validated, MovieSchema)
        assert validated.tmdb_id == 694

    @staticmethod
    def test_extract_full_pipeline(
        aggregator: DataAggregator,
        sample_tmdb_movies: list[dict[str, Any]],
        sample_rt_data: dict[str, Any]
    ) -> None:
        """Test pipeline complet."""
        # Enrichir premier film seulement
        rt_enriched = [
            {**sample_tmdb_movies[0], **sample_rt_data}
        ]

        result = aggregator.extract(
            tmdb_movies=sample_tmdb_movies,
            rt_enriched=rt_enriched
        )

        assert len(result) > 0
        assert aggregator.stats.tmdb_movies == len(sample_tmdb_movies)
        assert aggregator.stats.rt_enriched == 1
        assert result[0]["tomatometer_score"] == 85
