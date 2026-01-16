"""Unit tests for aggregation Pydantic schemas."""

from datetime import date

import pytest
from pytest import approx
from pydantic import ValidationError

from src.etl.aggregation.schemas import (
    IMDB_ID_PATTERN,
    AggregatedFilm,
    IMDBFilmData,
    KaggleFilmData,
    RTEnrichmentData,
    SparkFilmData,
    TMDBFilmData,
)


class TestIMDBIDPattern:
    """Tests for IMDB ID regex pattern."""

    @staticmethod
    def test_pattern_exists() -> None:
        """Test pattern constant is defined."""
        assert IMDB_ID_PATTERN == r"^tt\d{7,8}$"


class TestTMDBFilmData:
    """Tests for TMDBFilmData schema."""

    @staticmethod
    def test_minimal_valid() -> None:
        """Test minimal valid TMDB film."""
        film = TMDBFilmData(tmdb_id=123, title="Horror Movie")
        assert film.tmdb_id == 123
        assert film.title == "Horror Movie"
        assert film.vote_average == approx(0.0)

    @staticmethod
    def test_full_valid() -> None:
        """Test full TMDB film with all fields."""
        film = TMDBFilmData(
            tmdb_id=123,
            imdb_id="tt1234567",
            title="Horror Movie",
            original_title="Original",
            release_date=date(2024, 1, 15),
            overview="A scary film",
            tagline="Be afraid",
            popularity=100.5,
            vote_average=7.5,
            vote_count=1000,
            runtime=120,
            original_language="en",
            adult=False,
            status="Released",
            poster_path="/poster.jpg",
            backdrop_path="/backdrop.jpg",
            budget=1000000,
            revenue=5000000,
            genres=["Horror", "Thriller"],
            keywords=["scary", "ghost"],
        )
        assert film.imdb_id == "tt1234567"
        assert film.genres == ["Horror", "Thriller"]

    @staticmethod
    def test_year_property() -> None:
        """Test year extraction from release_date."""
        film = TMDBFilmData(
            tmdb_id=1,
            title="Test",
            release_date=date(2024, 6, 15),
        )
        assert film.year == 2024

    @staticmethod
    def test_year_property_none() -> None:
        """Test year is None when no release_date."""
        film = TMDBFilmData(tmdb_id=1, title="Test")
        assert film.year is None

    @staticmethod
    def test_tmdb_id_must_be_positive() -> None:
        """Test tmdb_id validation."""
        with pytest.raises(ValidationError):
            TMDBFilmData(tmdb_id=0, title="Test")

    @staticmethod
    def test_invalid_imdb_id_format() -> None:
        """Test imdb_id pattern validation."""
        with pytest.raises(ValidationError):
            TMDBFilmData(tmdb_id=1, title="Test", imdb_id="invalid")

    @staticmethod
    def test_vote_average_range() -> None:
        """Test vote_average must be 0-10."""
        with pytest.raises(ValidationError):
            TMDBFilmData(tmdb_id=1, title="Test", vote_average=11.0)

    @staticmethod
    def test_title_min_length() -> None:
        """Test title minimum length."""
        with pytest.raises(ValidationError):
            TMDBFilmData(tmdb_id=1, title="")

    @staticmethod
    def test_extra_fields_ignored() -> None:
        """Test extra fields are ignored."""
        film = TMDBFilmData(tmdb_id=1, title="Test", unknown_field="ignored")
        assert not hasattr(film, "unknown_field")


class TestRTEnrichmentData:
    """Tests for RTEnrichmentData schema."""

    @staticmethod
    def test_minimal_valid() -> None:
        """Test minimal RT data."""
        data = RTEnrichmentData(tmdb_id=123)
        assert data.tmdb_id == 123
        assert data.tomatometer_score is None

    @staticmethod
    def test_full_valid() -> None:
        """Test full RT data."""
        data = RTEnrichmentData(
            tmdb_id=123,
            tomatometer_score=85,
            tomatometer_state="certified_fresh",
            critics_count=200,
            critics_average_rating=7.5,
            audience_score=75,
            audience_state="upright",
            audience_count=5000,
            audience_average_rating=3.8,
            critics_consensus="A terrifying masterpiece.",
            rt_url="https://rottentomatoes.com/m/movie",
            rt_rating="R",
        )
        assert data.tomatometer_score == 85
        assert data.critics_consensus == "A terrifying masterpiece."

    @staticmethod
    def test_is_certified_fresh_true() -> None:
        """Test is_certified_fresh property when true."""
        data = RTEnrichmentData(tmdb_id=1, tomatometer_state="certified_fresh")
        assert data.is_certified_fresh is True

    @staticmethod
    def test_is_certified_fresh_false() -> None:
        """Test is_certified_fresh property when false."""
        data = RTEnrichmentData(tmdb_id=1, tomatometer_state="fresh")
        assert data.is_certified_fresh is False

    @staticmethod
    def test_has_scores_with_tomatometer() -> None:
        """Test has_scores with tomatometer only."""
        data = RTEnrichmentData(tmdb_id=1, tomatometer_score=80)
        assert data.has_scores is True

    @staticmethod
    def test_has_scores_with_audience() -> None:
        """Test has_scores with audience only."""
        data = RTEnrichmentData(tmdb_id=1, audience_score=70)
        assert data.has_scores is True

    @staticmethod
    def test_has_scores_none() -> None:
        """Test has_scores when no scores."""
        data = RTEnrichmentData(tmdb_id=1)
        assert data.has_scores is False

    @staticmethod
    def test_tomatometer_score_range() -> None:
        """Test tomatometer_score must be 0-100."""
        with pytest.raises(ValidationError):
            RTEnrichmentData(tmdb_id=1, tomatometer_score=101)

    @staticmethod
    def test_audience_average_rating_max() -> None:
        """Test audience_average_rating max is 5.0."""
        with pytest.raises(ValidationError):
            RTEnrichmentData(tmdb_id=1, audience_average_rating=5.5)


class TestIMDBFilmData:
    """Tests for IMDBFilmData schema."""

    @staticmethod
    def test_minimal_valid() -> None:
        """Test minimal IMDB film."""
        film = IMDBFilmData(imdb_id="tt1234567", title="Horror")
        assert film.imdb_id == "tt1234567"
        assert film.title == "Horror"

    @staticmethod
    def test_full_valid() -> None:
        """Test full IMDB film."""
        film = IMDBFilmData(
            imdb_id="tt1234567",
            tmdb_id=123,
            title="Horror Movie",
            year=2024,
            runtime=120,
            imdb_rating=8.5,
            imdb_votes=50000,
            genres="Horror, Thriller, Mystery",
        )
        assert film.imdb_rating == approx(8.5)

    @staticmethod
    def test_genres_list_property() -> None:
        """Test genres_list parsing."""
        film = IMDBFilmData(
            imdb_id="tt1234567",
            title="Test",
            genres="Horror, Thriller, Mystery",
        )
        assert film.genres_list == ["Horror", "Thriller", "Mystery"]

    @staticmethod
    def test_genres_list_empty() -> None:
        """Test genres_list when None."""
        film = IMDBFilmData(imdb_id="tt1234567", title="Test")
        assert film.genres_list == []

    @staticmethod
    def test_genres_list_strips_whitespace() -> None:
        """Test genres_list strips whitespace."""
        film = IMDBFilmData(
            imdb_id="tt1234567",
            title="Test",
            genres="  Horror  ,  Thriller  ",
        )
        assert film.genres_list == ["Horror", "Thriller"]

    @staticmethod
    def test_year_range_min() -> None:
        """Test year minimum is 1888."""
        with pytest.raises(ValidationError):
            IMDBFilmData(imdb_id="tt1234567", title="Test", year=1800)

    @staticmethod
    def test_year_range_max() -> None:
        """Test year maximum is 2030."""
        with pytest.raises(ValidationError):
            IMDBFilmData(imdb_id="tt1234567", title="Test", year=2031)

    @staticmethod
    def test_imdb_id_8_digits() -> None:
        """Test 8-digit IMDB ID is valid."""
        film = IMDBFilmData(imdb_id="tt12345678", title="Test")
        assert film.imdb_id == "tt12345678"


class TestKaggleFilmData:
    """Tests for KaggleFilmData schema."""

    @staticmethod
    def test_with_tmdb_id() -> None:
        """Test Kaggle film with tmdb_id."""
        film = KaggleFilmData(tmdb_id=123, title="Horror")
        assert film.tmdb_id == 123

    @staticmethod
    def test_with_imdb_id() -> None:
        """Test Kaggle film with imdb_id."""
        film = KaggleFilmData(imdb_id="tt1234567", title="Horror")
        assert film.imdb_id == "tt1234567"

    @staticmethod
    def test_with_both_ids() -> None:
        """Test Kaggle film with both identifiers."""
        film = KaggleFilmData(tmdb_id=123, imdb_id="tt1234567", title="Horror")
        assert film.tmdb_id == 123
        assert film.imdb_id == "tt1234567"

    @staticmethod
    def test_missing_both_ids_raises() -> None:
        """Test validation error when no identifier."""
        with pytest.raises(ValidationError) as exc_info:
            KaggleFilmData(title="Horror")
        assert "At least tmdb_id or imdb_id required" in str(exc_info.value)

    @staticmethod
    def test_full_valid() -> None:
        """Test full Kaggle film."""
        film = KaggleFilmData(
            tmdb_id=123,
            title="Horror Movie",
            year=2024,
            runtime=90,
            rating=7.5,
            votes=1000,
            overview="Synopsis",
            genres=["Horror"],
        )
        assert film.rating == approx(7.5)


class TestSparkFilmData:
    """Tests for SparkFilmData schema."""

    @staticmethod
    def test_minimal_valid() -> None:
        """Test minimal Spark film."""
        film = SparkFilmData(title="Horror")
        assert film.title == "Horror"
        assert film.tmdb_id is None

    @staticmethod
    def test_full_valid() -> None:
        """Test full Spark film."""
        film = SparkFilmData(
            tmdb_id=123,
            imdb_id="tt1234567",
            title="Horror Movie",
            year=2024,
            rating=7.5,
            votes=1000,
            budget=1000000,
            revenue=5000000,
        )
        assert film.budget == 1000000
        assert film.revenue == 5000000


class TestAggregatedFilm:
    """Tests for AggregatedFilm schema."""

    @staticmethod
    def test_minimal_valid() -> None:
        """Test minimal aggregated film."""
        film = AggregatedFilm(tmdb_id=123, title="Horror")
        assert film.tmdb_id == 123
        assert film.sources == []

    @staticmethod
    def test_full_valid() -> None:
        """Test full aggregated film."""
        film = AggregatedFilm(
            tmdb_id=123,
            imdb_id="tt1234567",
            title="Horror Movie",
            original_title="Original",
            release_date=date(2024, 1, 15),
            overview="Synopsis",
            critics_consensus="Terrifying.",
            popularity=100.0,
            vote_average=7.5,
            vote_count=1000,
            tomatometer_score=85,
            tomatometer_state="certified_fresh",
            audience_score=75,
            imdb_rating=8.0,
            imdb_votes=50000,
            budget=1000000,
            revenue=5000000,
            genres=["Horror"],
            keywords=["scary"],
            aggregated_score=8.2,
            sources=["tmdb", "rt", "imdb"],
            enrichment_count=3,
        )
        assert film.aggregated_score == approx(8.2)

    @staticmethod
    def test_year_property() -> None:
        """Test year extraction."""
        film = AggregatedFilm(
            tmdb_id=1,
            title="Test",
            release_date=date(2024, 6, 15),
        )
        assert film.year == 2024

    @staticmethod
    def test_year_property_none() -> None:
        """Test year is None without release_date."""
        film = AggregatedFilm(tmdb_id=1, title="Test")
        assert film.year is None

    @staticmethod
    def test_is_certified_fresh() -> None:
        """Test is_certified_fresh property."""
        film = AggregatedFilm(
            tmdb_id=1,
            title="Test",
            tomatometer_state="certified_fresh",
        )
        assert film.is_certified_fresh is True

    @staticmethod
    def test_has_rt_data_with_rt() -> None:
        """Test has_rt_data with 'rt' source."""
        film = AggregatedFilm(tmdb_id=1, title="Test", sources=["tmdb", "rt"])
        assert film.has_rt_data is True

    @staticmethod
    def test_has_rt_data_with_rotten_tomatoes() -> None:
        """Test has_rt_data with 'rotten_tomatoes' source."""
        film = AggregatedFilm(
            tmdb_id=1,
            title="Test",
            sources=["rotten_tomatoes"],
        )
        assert film.has_rt_data is True

    @staticmethod
    def test_has_rt_data_false() -> None:
        """Test has_rt_data when not enriched."""
        film = AggregatedFilm(tmdb_id=1, title="Test", sources=["tmdb"])
        assert film.has_rt_data is False

    @staticmethod
    def test_has_imdb_data() -> None:
        """Test has_imdb_data property."""
        film = AggregatedFilm(tmdb_id=1, title="Test", sources=["imdb"])
        assert film.has_imdb_data is True

    @staticmethod
    def test_has_imdb_data_false() -> None:
        """Test has_imdb_data when not enriched."""
        film = AggregatedFilm(tmdb_id=1, title="Test", sources=["tmdb"])
        assert film.has_imdb_data is False

    @staticmethod
    def test_roi_calculation() -> None:
        """Test ROI calculation."""
        film = AggregatedFilm(
            tmdb_id=1,
            title="Test",
            budget=1000000,
            revenue=5000000,
        )
        assert film.roi == approx(5.0)

    @staticmethod
    def test_roi_zero_budget() -> None:
        """Test ROI is None with zero budget."""
        film = AggregatedFilm(tmdb_id=1, title="Test", budget=0, revenue=5000000)
        assert film.roi is None

    @staticmethod
    def test_rag_text_full() -> None:
        """Test rag_text with all parts."""
        film = AggregatedFilm(
            tmdb_id=1,
            title="Horror Movie",
            critics_consensus="Terrifying masterpiece.",
            overview="A scary film about ghosts.",
            tagline="Be afraid.",
        )
        expected = (
            "Horror Movie Terrifying masterpiece. "
            "A scary film about ghosts. Be afraid."
        )
        assert film.rag_text == expected

    @staticmethod
    def test_rag_text_title_only() -> None:
        """Test rag_text with title only."""
        film = AggregatedFilm(tmdb_id=1, title="Horror Movie")
        assert film.rag_text == "Horror Movie"

    @staticmethod
    def test_sources_validator_string() -> None:
        """Test sources validator converts string to list."""
        film = AggregatedFilm(tmdb_id=1, title="Test", sources="tmdb")
        assert film.sources == ["tmdb"]

    @staticmethod
    def test_sources_validator_none() -> None:
        """Test sources validator handles None."""
        film = AggregatedFilm(tmdb_id=1, title="Test", sources=None)
        assert film.sources == []

    @staticmethod
    def test_sources_validator_list() -> None:
        """Test sources validator preserves list."""
        film = AggregatedFilm(tmdb_id=1, title="Test", sources=["a", "b"])
        assert film.sources == ["a", "b"]

    @staticmethod
    def test_aggregated_score_range() -> None:
        """Test aggregated_score must be 0-10."""
        with pytest.raises(ValidationError):
            AggregatedFilm(tmdb_id=1, title="Test", aggregated_score=11.0)
