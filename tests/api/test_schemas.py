"""Unit tests for API Pydantic schemas."""

from datetime import date, datetime

import pytest
from pytest import approx
from pydantic import ValidationError

from src.api.schemas import (
    FilmBase,
    FilmDetail,
    FilmListResponse,
    HealthResponse,
    PaginatedMeta,
    PaginationParams,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    TokenRequest,
    TokenResponse,
)


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    @staticmethod
    def test_default_timestamp() -> None:
        """Test timestamp is auto-generated."""
        response = HealthResponse(status="healthy", version="1.0.0")
        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert isinstance(response.timestamp, datetime)

    @staticmethod
    def test_custom_timestamp() -> None:
        """Test custom timestamp can be provided."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        response = HealthResponse(status="ok", version="2.0.0", timestamp=ts)
        assert response.timestamp == ts


class TestTokenRequest:
    """Tests for TokenRequest schema."""

    @staticmethod
    def test_valid_credentials() -> None:
        """Test valid username and password."""
        request = TokenRequest(username="testuser", password="securepass123")
        assert request.username == "testuser"
        assert request.password == "securepass123"

    @staticmethod
    def test_username_too_short() -> None:
        """Test username minimum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            TokenRequest(username="ab", password="securepass123")
        assert "username" in str(exc_info.value)

    @staticmethod
    def test_username_too_long() -> None:
        """Test username maximum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            TokenRequest(username="a" * 51, password="securepass123")
        assert "username" in str(exc_info.value)

    @staticmethod
    def test_password_too_short() -> None:
        """Test password minimum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            TokenRequest(username="testuser", password="short")
        assert "password" in str(exc_info.value)

    @staticmethod
    def test_password_too_long() -> None:
        """Test password maximum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            TokenRequest(username="testuser", password="a" * 101)
        assert "password" in str(exc_info.value)


class TestTokenResponse:
    """Tests for TokenResponse schema."""

    @staticmethod
    def test_default_token_type() -> None:
        """Test default token type is bearer."""
        response = TokenResponse(access_token="jwt_token", expires_in=3600)
        assert response.token_type == "bearer"

    @staticmethod
    def test_custom_token_type() -> None:
        """Test custom token type."""
        response = TokenResponse(
            access_token="token",
            token_type="custom",
            expires_in=7200,
        )
        assert response.token_type == "custom"
        assert response.expires_in == 7200


class TestPaginationParams:
    """Tests for PaginationParams schema."""

    @staticmethod
    def test_default_values() -> None:
        """Test default pagination values."""
        params = PaginationParams()
        assert params.page == 1
        assert params.size == 20

    @staticmethod
    def test_offset_calculation_first_page() -> None:
        """Test offset is 0 for first page."""
        params = PaginationParams(page=1, size=20)
        assert params.offset == 0

    @staticmethod
    def test_offset_calculation_second_page() -> None:
        """Test offset calculation for page 2."""
        params = PaginationParams(page=2, size=20)
        assert params.offset == 20

    @staticmethod
    def test_offset_calculation_custom_size() -> None:
        """Test offset with custom page size."""
        params = PaginationParams(page=3, size=50)
        assert params.offset == 100

    @staticmethod
    def test_page_minimum() -> None:
        """Test page minimum validation."""
        with pytest.raises(ValidationError):
            PaginationParams(page=0)

    @staticmethod
    def test_page_maximum() -> None:
        """Test page maximum validation."""
        with pytest.raises(ValidationError):
            PaginationParams(page=1001)

    @staticmethod
    def test_size_minimum() -> None:
        """Test size minimum validation."""
        with pytest.raises(ValidationError):
            PaginationParams(size=0)

    @staticmethod
    def test_size_maximum() -> None:
        """Test size maximum validation."""
        with pytest.raises(ValidationError):
            PaginationParams(size=101)


class TestPaginatedMeta:
    """Tests for PaginatedMeta schema."""

    @staticmethod
    def test_from_params_basic() -> None:
        """Test meta creation from params."""
        params = PaginationParams(page=1, size=10)
        meta = PaginatedMeta.from_params(params, total=100)
        assert meta.page == 1
        assert meta.size == 10
        assert meta.total == 100
        assert meta.pages == 10

    @staticmethod
    def test_from_params_partial_page() -> None:
        """Test pages calculation with partial last page."""
        params = PaginationParams(page=1, size=10)
        meta = PaginatedMeta.from_params(params, total=95)
        assert meta.pages == 10

    @staticmethod
    def test_from_params_zero_total() -> None:
        """Test pages is 0 when total is 0."""
        params = PaginationParams(page=1, size=10)
        meta = PaginatedMeta.from_params(params, total=0)
        assert meta.pages == 0

    @staticmethod
    def test_from_params_exact_pages() -> None:
        """Test exact page division."""
        params = PaginationParams(page=1, size=25)
        meta = PaginatedMeta.from_params(params, total=75)
        assert meta.pages == 3


class TestFilmBase:
    """Tests for FilmBase schema."""

    @staticmethod
    def test_minimal_film() -> None:
        """Test film with required fields only."""
        film = FilmBase(id=1, tmdb_id=123, title="Horror Movie")
        assert film.id == 1
        assert film.tmdb_id == 123
        assert film.title == "Horror Movie"
        assert film.release_date is None

    @staticmethod
    def test_full_film() -> None:
        """Test film with all fields."""
        film = FilmBase(
            id=1,
            tmdb_id=123,
            title="Horror Movie",
            release_date=date(2024, 1, 1),
            vote_average=7.5,
            popularity=100.5,
            poster_path="/poster.jpg",
        )
        assert film.release_date == date(2024, 1, 1)
        assert film.vote_average == approx(7.5)

    @staticmethod
    def test_from_attributes_config() -> None:
        """Test from_attributes is enabled."""
        assert FilmBase.model_config.get("from_attributes") is True


class TestFilmDetail:
    """Tests for FilmDetail schema."""

    @staticmethod
    def test_inherits_base_fields() -> None:
        """Test FilmDetail includes base fields."""
        film = FilmDetail(
            id=1,
            tmdb_id=123,
            title="Horror Movie",
            overview="A scary film",
            runtime=120,
        )
        assert film.id == 1
        assert film.overview == "A scary film"
        assert film.runtime == 120

    @staticmethod
    def test_all_optional_fields() -> None:
        """Test all detail fields are optional."""
        film = FilmDetail(id=1, tmdb_id=123, title="Movie")
        assert film.imdb_id is None
        assert film.original_title is None
        assert film.overview is None
        assert film.runtime is None
        assert film.budget is None
        assert film.revenue is None
        assert film.vote_count is None
        assert film.tagline is None
        assert film.status is None
        assert film.original_language is None


class TestFilmListResponse:
    """Tests for FilmListResponse schema."""

    @staticmethod
    def test_empty_list() -> None:
        """Test response with empty data."""
        meta = PaginatedMeta(page=1, size=20, total=0, pages=0)
        response = FilmListResponse(data=[], meta=meta)
        assert len(response.data) == 0
        assert response.meta.total == 0

    @staticmethod
    def test_with_films() -> None:
        """Test response with film data."""
        films = [FilmBase(id=i, tmdb_id=i * 10, title=f"Film {i}") for i in range(3)]
        meta = PaginatedMeta(page=1, size=20, total=3, pages=1)
        response = FilmListResponse(data=films, meta=meta)
        assert len(response.data) == 3
        assert response.data[0].title == "Film 0"


class TestSearchRequest:
    """Tests for SearchRequest schema."""

    @staticmethod
    def test_valid_request() -> None:
        """Test valid search request."""
        request = SearchRequest(query="scary horror movie")
        assert request.query == "scary horror movie"
        assert request.limit == 10

    @staticmethod
    def test_custom_limit() -> None:
        """Test custom limit."""
        request = SearchRequest(query="test", limit=25)
        assert request.limit == 25

    @staticmethod
    def test_query_too_short() -> None:
        """Test query minimum length."""
        with pytest.raises(ValidationError):
            SearchRequest(query="a")

    @staticmethod
    def test_query_too_long() -> None:
        """Test query maximum length."""
        with pytest.raises(ValidationError):
            SearchRequest(query="a" * 501)

    @staticmethod
    def test_limit_minimum() -> None:
        """Test limit minimum validation."""
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=0)

    @staticmethod
    def test_limit_maximum() -> None:
        """Test limit maximum validation."""
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=51)


class TestSearchResultItem:
    """Tests for SearchResultItem schema."""

    @staticmethod
    def test_minimal_result() -> None:
        """Test result with required fields."""
        result = SearchResultItem(id=1, tmdb_id=123, title="Movie", score=0.85)
        assert result.id == 1
        assert result.score == approx(0.85)
        assert result.overview is None

    @staticmethod
    def test_full_result() -> None:
        """Test result with all fields."""
        result = SearchResultItem(
            id=1,
            tmdb_id=123,
            title="Movie",
            overview="Synopsis",
            release_date=date(2024, 1, 1),
            score=0.95,
        )
        assert result.overview == "Synopsis"
        assert result.release_date == date(2024, 1, 1)


class TestSearchResponse:
    """Tests for SearchResponse schema."""

    @staticmethod
    def test_empty_results() -> None:
        """Test response with no results."""
        response = SearchResponse(query="test", results=[], count=0)
        assert response.query == "test"
        assert response.count == 0

    @staticmethod
    def test_with_results() -> None:
        """Test response with search results."""
        results = [
            SearchResultItem(id=1, tmdb_id=10, title="Film 1", score=0.9),
            SearchResultItem(id=2, tmdb_id=20, title="Film 2", score=0.8),
        ]
        response = SearchResponse(query="horror", results=results, count=2)
        assert len(response.results) == 2
        assert response.results[0].score == approx(0.9)
