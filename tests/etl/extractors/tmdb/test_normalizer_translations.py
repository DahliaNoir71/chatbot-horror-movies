"""Unit tests for FR translations & alternative_titles extraction."""

from typing import Any

import pytest

from src.etl.extractors.tmdb.normalizer import TMDBNormalizer


@pytest.fixture()
def normalizer() -> TMDBNormalizer:
    return TMDBNormalizer()


def _translation(
    iso_639_1: str,
    iso_3166_1: str,
    *,
    title: str | None = None,
    overview: str | None = None,
) -> dict[str, Any]:
    """Build a TMDB translation entry."""
    data: dict[str, Any] = {}
    if title is not None:
        data["title"] = title
    if overview is not None:
        data["overview"] = overview
    return {
        "iso_639_1": iso_639_1,
        "iso_3166_1": iso_3166_1,
        "data": data,
    }


def _alt_title(iso_3166_1: str, title: str) -> dict[str, Any]:
    return {"iso_3166_1": iso_3166_1, "title": title}


class TestExtractFrenchTitle:
    """_extract_french_title: iterate translations, match fr + FR/BE/CA."""

    @staticmethod
    def test_extract_french_title_fr_fr() -> None:
        translations = {
            "translations": [
                _translation("fr", "FR", title="Sans un bruit"),
            ],
        }
        assert TMDBNormalizer._extract_french_title(translations) == "Sans un bruit"

    @staticmethod
    def test_extract_french_title_fallback_be() -> None:
        translations = {
            "translations": [
                _translation("en", "US", title="A Quiet Place"),
                _translation("fr", "BE", title="Un Endroit Silencieux"),
            ],
        }
        result = TMDBNormalizer._extract_french_title(translations)
        assert result == "Un Endroit Silencieux"

    @staticmethod
    def test_extract_french_title_none_when_missing() -> None:
        assert TMDBNormalizer._extract_french_title(None) is None
        assert TMDBNormalizer._extract_french_title({"translations": []}) is None
        only_english = {
            "translations": [_translation("en", "US", title="Halloween")],
        }
        assert TMDBNormalizer._extract_french_title(only_english) is None

    @staticmethod
    def test_extract_french_title_ignores_fr_from_other_country() -> None:
        # fr-CH is out of FR_TRANSLATION_COUNTRIES (FR/BE/CA only)
        translations = {
            "translations": [_translation("fr", "CH", title="Titre Suisse")],
        }
        assert TMDBNormalizer._extract_french_title(translations) is None

    @staticmethod
    def test_extract_french_title_strips_whitespace() -> None:
        translations = {
            "translations": [_translation("fr", "FR", title="  L'Exorciste  ")],
        }
        assert TMDBNormalizer._extract_french_title(translations) == "L'Exorciste"

    @staticmethod
    def test_extract_french_title_skips_empty_data() -> None:
        translations = {
            "translations": [
                _translation("fr", "FR", title=""),
                _translation("fr", "CA", title="L'Exorciste"),
            ],
        }
        assert TMDBNormalizer._extract_french_title(translations) == "L'Exorciste"


class TestExtractFrenchOverview:
    """_extract_french_overview: same logic on data.overview."""

    @staticmethod
    def test_extract_french_overview_fr_fr() -> None:
        translations = {
            "translations": [
                _translation("fr", "FR", overview="Un prêtre affronte le démon."),
            ],
        }
        result = TMDBNormalizer._extract_french_overview(translations)
        assert result == "Un prêtre affronte le démon."

    @staticmethod
    def test_extract_french_overview_none_when_missing() -> None:
        assert TMDBNormalizer._extract_french_overview(None) is None
        assert TMDBNormalizer._extract_french_overview({"translations": []}) is None


class TestExtractAlternativeTitles:
    """_extract_alternative_titles: FR/BE/CA/CH/LU, deduplicated, order-preserving."""

    @staticmethod
    def test_extract_alternative_titles_deduplicates() -> None:
        alt = {
            "titles": [
                _alt_title("FR", "Ça"),
                _alt_title("BE", "Ça"),
                _alt_title("CA", "Ça"),
            ],
        }
        assert TMDBNormalizer._extract_alternative_titles(alt) == ["Ça"]

    @staticmethod
    def test_extract_alternative_titles_order_preserving() -> None:
        alt = {
            "titles": [
                _alt_title("FR", "Titre A"),
                _alt_title("BE", "Titre B"),
                _alt_title("CH", "Titre C"),
                _alt_title("LU", "Titre D"),
            ],
        }
        result = TMDBNormalizer._extract_alternative_titles(alt)
        assert result == ["Titre A", "Titre B", "Titre C", "Titre D"]

    @staticmethod
    def test_extract_alternative_titles_filters_non_francophone() -> None:
        alt = {
            "titles": [
                _alt_title("US", "American Title"),
                _alt_title("GB", "British Title"),
                _alt_title("FR", "Titre Français"),
            ],
        }
        assert TMDBNormalizer._extract_alternative_titles(alt) == ["Titre Français"]

    @staticmethod
    def test_extract_alternative_titles_empty_inputs() -> None:
        assert TMDBNormalizer._extract_alternative_titles(None) == []
        assert TMDBNormalizer._extract_alternative_titles({"titles": []}) == []

    @staticmethod
    def test_extract_alternative_titles_skips_empty_strings() -> None:
        alt = {
            "titles": [
                _alt_title("FR", ""),
                _alt_title("BE", "   "),
                _alt_title("CA", "Canadian Title"),
            ],
        }
        assert TMDBNormalizer._extract_alternative_titles(alt) == ["Canadian Title"]


class TestNormalizeFilmIntegratesFrFields:
    """normalize_film: wires translations + alternative_titles through."""

    @staticmethod
    def test_normalize_film_integrates_fr_fields(normalizer: TMDBNormalizer) -> None:
        raw = {
            "id": 9552,
            "title": "The Exorcist",
            "overview": "A young girl is possessed.",
            "release_date": "1973-12-26",
            "popularity": 45.0,
            "vote_average": 8.0,
            "vote_count": 10_000,
            "adult": False,
            "genre_ids": [27],
            "translations": {
                "translations": [
                    _translation("en", "US", title="The Exorcist"),
                    _translation(
                        "fr", "FR",
                        title="L'Exorciste",
                        overview="Une jeune fille est possédée.",
                    ),
                ],
            },
            "alternative_titles": {
                "titles": [
                    _alt_title("FR", "L'Exorciste: Version Intégrale"),
                    _alt_title("US", "The Exorcist: Director's Cut"),
                ],
            },
        }

        result = normalizer.normalize_film(raw)

        assert result["title"] == "The Exorcist"
        assert result["title_fr"] == "L'Exorciste"
        assert result["overview_fr"] == "Une jeune fille est possédée."
        assert result["alternative_titles"] == ["L'Exorciste: Version Intégrale"]

    @staticmethod
    def test_normalize_film_without_translations(normalizer: TMDBNormalizer) -> None:
        """When append_to_response data is absent, FR fields are None/empty."""
        raw = {
            "id": 123,
            "title": "Discover-only film",
            "overview": None,
            "release_date": "2020-01-01",
            "popularity": 1.0,
            "vote_average": 0.0,
            "vote_count": 0,
            "adult": False,
            "genre_ids": [27],
        }
        result = normalizer.normalize_film(raw)

        assert result["title_fr"] is None
        assert result["overview_fr"] is None
        assert result["alternative_titles"] == []
