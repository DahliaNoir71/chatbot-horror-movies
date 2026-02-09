"""Unit tests for TMDB normalizer."""

from datetime import date

import pytest

from src.etl.extractors.tmdb.normalizer import TMDBNormalizer


@pytest.fixture()
def normalizer() -> TMDBNormalizer:
    return TMDBNormalizer()


def _make_film(**overrides) -> dict:
    base = {
        "id": 123,
        "title": "The Shining",
        "overview": "A family heads to an isolated hotel.",
        "release_date": "1980-05-23",
        "popularity": 45.6,
        "vote_average": 8.4,
        "vote_count": 15000,
        "adult": False,
        "genre_ids": [27, 53],
    }
    base.update(overrides)
    return base


def _make_cast(count: int = 1, **overrides) -> list[dict]:
    return [
        {
            "id": 100 + i,
            "name": f"Actor {i}",
            "character": f"Character {i}",
            "order": i,
        }
        | overrides
        for i in range(count)
    ]


def _make_crew(job: str = "Director", **overrides) -> list[dict]:
    base = {"id": 200, "name": "John Doe", "department": "Directing", "job": job}
    base.update(overrides)
    return [base]


# -------------------------------------------------------------------------
# Film Normalization
# -------------------------------------------------------------------------


class TestNormalizeFilm:
    @staticmethod
    def test_basic_normalization(normalizer: TMDBNormalizer) -> None:
        raw = _make_film()
        result = normalizer.normalize_film(raw)
        assert result["tmdb_id"] == 123
        assert result["title"] == "The Shining"
        assert result["release_date"] == date(1980, 5, 23)
        assert result["source"] == "tmdb_discover"

    @staticmethod
    def test_custom_source(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(), source="tmdb_details")
        assert result["source"] == "tmdb_details"

    @staticmethod
    def test_optional_fields_defaults(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film())
        assert result["imdb_id"] is None
        assert result["tagline"] is None
        assert result["budget"] == 0
        assert result["revenue"] == 0

    @staticmethod
    def test_with_all_optional_fields(normalizer: TMDBNormalizer) -> None:
        raw = _make_film(
            imdb_id="tt0081505",
            original_title="The Shining",
            tagline="A masterpiece of horror.",
            runtime=146,
            original_language="en",
            status="Released",
            poster_path="/poster.jpg",
            backdrop_path="/bg.jpg",
            homepage="https://example.com",
            budget=19000000,
            revenue=44000000,
        )
        result = normalizer.normalize_film(raw)
        assert result["imdb_id"] == "tt0081505"
        assert result["runtime"] == 146
        assert result["budget"] == 19000000

    @staticmethod
    def test_invalid_date_returns_none(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(release_date="not-a-date"))
        assert result["release_date"] is None

    @staticmethod
    def test_empty_date_returns_none(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(release_date=""))
        assert result["release_date"] is None

    @staticmethod
    def test_none_date_returns_none(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(release_date=None))
        assert result["release_date"] is None

    @staticmethod
    def test_runtime_zero_returns_none(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(runtime=0))
        assert result["runtime"] is None

    @staticmethod
    def test_runtime_negative_returns_none(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(runtime=-10))
        assert result["runtime"] is None

    @staticmethod
    def test_runtime_over_1000_returns_none(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(runtime=1001))
        assert result["runtime"] is None

    @staticmethod
    def test_runtime_valid(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(runtime=120))
        assert result["runtime"] == 120

    @staticmethod
    def test_whitespace_title_cleaned(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(title="  The Shining  "))
        assert result["title"] == "The Shining"

    @staticmethod
    def test_empty_title_becomes_none(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(title="   "))
        assert result["title"] is None

    @staticmethod
    def test_none_overview(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_film(_make_film(overview=None))
        assert result["overview"] is None


class TestNormalizeFilms:
    @staticmethod
    def test_multiple_films(normalizer: TMDBNormalizer) -> None:
        films = [_make_film(id=1, title="Film A"), _make_film(id=2, title="Film B")]
        result = normalizer.normalize_films(films)
        assert len(result) == 2
        assert result[0]["tmdb_id"] == 1
        assert result[1]["tmdb_id"] == 2

    @staticmethod
    def test_invalid_film_skipped(normalizer: TMDBNormalizer) -> None:
        films = [_make_film(), {"bad": "data"}]
        result = normalizer.normalize_films(films)
        assert len(result) == 1

    @staticmethod
    def test_empty_list(normalizer: TMDBNormalizer) -> None:
        assert normalizer.normalize_films([]) == []


# -------------------------------------------------------------------------
# Credits Normalization
# -------------------------------------------------------------------------


class TestNormalizeCredits:
    @staticmethod
    def test_directors_extracted(normalizer: TMDBNormalizer) -> None:
        crew = _make_crew("Director")
        result = normalizer.normalize_credits([], crew)
        assert len(result) == 1
        assert result[0]["role_type"] == "director"
        assert result[0]["person_name"] == "John Doe"

    @staticmethod
    def test_writers_extracted(normalizer: TMDBNormalizer) -> None:
        crew = [
            {"id": 1, "name": "Writer A", "department": "Writing", "job": "Screenplay"},
            {"id": 2, "name": "Writer B", "department": "Writing", "job": "Story"},
        ]
        result = normalizer.normalize_credits([], crew)
        assert len(result) == 2
        assert all(c["role_type"] == "writer" for c in result)

    @staticmethod
    def test_producers_extracted(normalizer: TMDBNormalizer) -> None:
        crew = [
            {"id": 1, "name": "Prod A", "department": "Production", "job": "Producer"},
            {"id": 2, "name": "Prod B", "department": "Production", "job": "Executive Producer"},
        ]
        result = normalizer.normalize_credits([], crew)
        assert len(result) == 2
        assert all(c["role_type"] == "producer" for c in result)

    @staticmethod
    def test_actors_extracted(normalizer: TMDBNormalizer) -> None:
        cast = _make_cast(3)
        result = normalizer.normalize_credits(cast, [])
        assert len(result) == 3
        assert all(c["role_type"] == "actor" for c in result)

    @staticmethod
    def test_actors_limited_to_max(normalizer: TMDBNormalizer) -> None:
        cast = _make_cast(15)
        result = normalizer.normalize_credits(cast, [])
        assert len(result) == TMDBNormalizer.MAX_ACTORS

    @staticmethod
    def test_actors_sorted_by_order(normalizer: TMDBNormalizer) -> None:
        cast = [
            {"id": 1, "name": "Last", "character": "C", "order": 5},
            {"id": 2, "name": "First", "character": "A", "order": 0},
        ]
        result = normalizer.normalize_credits(cast, [])
        assert result[0]["person_name"] == "First"
        assert result[1]["person_name"] == "Last"

    @staticmethod
    def test_combined_credits(normalizer: TMDBNormalizer) -> None:
        crew = _make_crew("Director")
        cast = _make_cast(2)
        result = normalizer.normalize_credits(cast, crew)
        roles = [c["role_type"] for c in result]
        assert "director" in roles
        assert "actor" in roles

    @staticmethod
    def test_unknown_role_type_returns_empty(normalizer: TMDBNormalizer) -> None:
        result = normalizer._get_job_filter("unknown")
        assert result == set()

    @staticmethod
    def test_actor_character_name(normalizer: TMDBNormalizer) -> None:
        cast = [{"id": 1, "name": "Jack", "character": "Danny", "order": 0}]
        result = normalizer.normalize_credits(cast, [])
        assert result[0]["character_name"] == "Danny"

    @staticmethod
    def test_crew_has_no_character(normalizer: TMDBNormalizer) -> None:
        crew = _make_crew("Director")
        result = normalizer.normalize_credits([], crew)
        assert result[0]["character_name"] is None


# -------------------------------------------------------------------------
# Reference Data Normalization
# -------------------------------------------------------------------------


class TestNormalizeRefData:
    @staticmethod
    def test_genre(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_genre({"id": 27, "name": "Horror"})
        assert result["tmdb_genre_id"] == 27
        assert result["name"] == "Horror"

    @staticmethod
    def test_genres_list(normalizer: TMDBNormalizer) -> None:
        genres = [{"id": 27, "name": "Horror"}, {"id": 53, "name": "Thriller"}]
        result = normalizer.normalize_genres(genres)
        assert len(result) == 2

    @staticmethod
    def test_keyword(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_keyword({"id": 1, "name": "ghost"})
        assert result["tmdb_keyword_id"] == 1
        assert result["name"] == "ghost"

    @staticmethod
    def test_keywords_list(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_keywords([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}])
        assert len(result) == 2

    @staticmethod
    def test_company(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_company({"id": 1, "name": "Blumhouse", "origin_country": "US"})
        assert result["tmdb_company_id"] == 1
        assert result["name"] == "Blumhouse"
        assert result["origin_country"] == "US"

    @staticmethod
    def test_companies_list(normalizer: TMDBNormalizer) -> None:
        result = normalizer.normalize_companies([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
        assert len(result) == 2

    @staticmethod
    def test_language_with_english_name(normalizer: TMDBNormalizer) -> None:
        result = TMDBNormalizer.normalize_language(
            {"iso_639_1": "en", "name": "English", "english_name": "English"}
        )
        assert result["iso_639_1"] == "en"
        assert result["name"] == "English"

    @staticmethod
    def test_language_fallback_to_name(normalizer: TMDBNormalizer) -> None:
        result = TMDBNormalizer.normalize_language({"iso_639_1": "fr", "name": "Français"})
        assert result["name"] == "Français"

    @staticmethod
    def test_languages_list(normalizer: TMDBNormalizer) -> None:
        langs = [
            {"iso_639_1": "en", "name": "English"},
            {"iso_639_1": "fr", "name": "French"},
        ]
        result = normalizer.normalize_languages(langs)
        assert len(result) == 2


# -------------------------------------------------------------------------
# Utility Methods
# -------------------------------------------------------------------------


class TestUtilityMethods:
    @staticmethod
    def test_clean_string_strips(normalizer: TMDBNormalizer) -> None:
        assert TMDBNormalizer._clean_string("  hello  ") == "hello"

    @staticmethod
    def test_clean_string_none() -> None:
        assert TMDBNormalizer._clean_string(None) is None

    @staticmethod
    def test_clean_string_empty_returns_none() -> None:
        assert TMDBNormalizer._clean_string("  ") is None

    @staticmethod
    def test_parse_date_valid() -> None:
        assert TMDBNormalizer._parse_date("2024-01-15") == date(2024, 1, 15)

    @staticmethod
    def test_parse_date_none() -> None:
        assert TMDBNormalizer._parse_date(None) is None

    @staticmethod
    def test_parse_date_invalid() -> None:
        assert TMDBNormalizer._parse_date("invalid") is None

    @staticmethod
    def test_validate_runtime_none() -> None:
        assert TMDBNormalizer._validate_runtime(None) is None

    @staticmethod
    def test_validate_runtime_zero() -> None:
        assert TMDBNormalizer._validate_runtime(0) is None

    @staticmethod
    def test_validate_runtime_negative() -> None:
        assert TMDBNormalizer._validate_runtime(-5) is None

    @staticmethod
    def test_validate_runtime_over_limit() -> None:
        assert TMDBNormalizer._validate_runtime(1001) is None

    @staticmethod
    def test_validate_runtime_valid() -> None:
        assert TMDBNormalizer._validate_runtime(120) == 120

    @staticmethod
    def test_validate_runtime_boundary_1() -> None:
        assert TMDBNormalizer._validate_runtime(1) == 1

    @staticmethod
    def test_validate_runtime_boundary_1000() -> None:
        assert TMDBNormalizer._validate_runtime(1000) == 1000
