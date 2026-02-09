"""Unit tests for Kaggle CSV normalizer."""

import pytest

from src.etl.extractors.csv.normalizer import KaggleNormalizer


@pytest.fixture()
def normalizer() -> KaggleNormalizer:
    return KaggleNormalizer()


def _make_raw(**overrides) -> dict:
    base = {
        "id": 123,
        "title": "The Shining",
        "original_title": "The Shining",
        "original_language": "en",
        "overview": "A family heads to an isolated hotel for the winter.",
        "tagline": "A masterpiece of modern horror.",
        "release_date": "1980-05-23",
        "poster_path": "/poster.jpg",
        "backdrop_path": "/bg.jpg",
        "popularity": 45.6,
        "vote_average": 8.4,
        "vote_count": 15000,
        "budget": 19000000,
        "revenue": 44000000,
        "runtime": 146,
        "status": "Released",
        "adult": False,
    }
    base.update(overrides)
    return base


# -------------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------------


class TestValidation:
    @staticmethod
    def test_valid_record(normalizer: KaggleNormalizer) -> None:
        assert normalizer.normalize(_make_raw()) is not None

    @staticmethod
    def test_missing_id(normalizer: KaggleNormalizer) -> None:
        assert normalizer.normalize(_make_raw(id=None)) is None

    @staticmethod
    def test_zero_id(normalizer: KaggleNormalizer) -> None:
        assert normalizer.normalize(_make_raw(id=0)) is None

    @staticmethod
    def test_missing_title(normalizer: KaggleNormalizer) -> None:
        assert normalizer.normalize(_make_raw(title=None)) is None

    @staticmethod
    def test_empty_title(normalizer: KaggleNormalizer) -> None:
        assert normalizer.normalize(_make_raw(title="  ")) is None


# -------------------------------------------------------------------------
# normalize()
# -------------------------------------------------------------------------


class TestNormalize:
    @staticmethod
    def test_basic_fields(normalizer: KaggleNormalizer) -> None:
        result = normalizer.normalize(_make_raw())
        assert result["tmdb_id"] == 123
        assert result["title"] == "The Shining"
        assert result["source"] == "kaggle"

    @staticmethod
    def test_numeric_fields(normalizer: KaggleNormalizer) -> None:
        result = normalizer.normalize(_make_raw())
        assert result["popularity"] == 45.6
        assert result["vote_average"] == 8.4
        assert result["vote_count"] == 15000
        assert result["budget"] == 19000000
        assert result["revenue"] == 44000000

    @staticmethod
    def test_date_parsing_iso(normalizer: KaggleNormalizer) -> None:
        result = normalizer.normalize(_make_raw(release_date="2024-01-15"))
        assert result["release_date"] == "2024-01-15"

    @staticmethod
    def test_date_parsing_year_only(normalizer: KaggleNormalizer) -> None:
        result = normalizer.normalize(_make_raw(release_date="2024"))
        assert result["release_date"] == "2024-01-01"

    @staticmethod
    def test_date_parsing_none(normalizer: KaggleNormalizer) -> None:
        result = normalizer.normalize(_make_raw(release_date=None))
        assert result["release_date"] is None

    @staticmethod
    def test_date_parsing_invalid(normalizer: KaggleNormalizer) -> None:
        result = normalizer.normalize(_make_raw(release_date="not-a-date"))
        assert result["release_date"] is None

    @staticmethod
    def test_status_default(normalizer: KaggleNormalizer) -> None:
        result = normalizer.normalize(_make_raw(status=None))
        assert result["status"] == "Released"


# -------------------------------------------------------------------------
# normalize_batch()
# -------------------------------------------------------------------------


class TestNormalizeBatch:
    @staticmethod
    def test_batch(normalizer: KaggleNormalizer) -> None:
        records = [_make_raw(id=1), _make_raw(id=2)]
        result = normalizer.normalize_batch(records)
        assert len(result) == 2

    @staticmethod
    def test_batch_skips_invalid(normalizer: KaggleNormalizer) -> None:
        records = [_make_raw(id=1), _make_raw(id=None)]
        result = normalizer.normalize_batch(records)
        assert len(result) == 1

    @staticmethod
    def test_empty_batch(normalizer: KaggleNormalizer) -> None:
        assert normalizer.normalize_batch([]) == []


# -------------------------------------------------------------------------
# Type Conversion Helpers
# -------------------------------------------------------------------------


class TestSafeInt:
    @staticmethod
    def test_int() -> None:
        assert KaggleNormalizer._safe_int(42, 0) == 42

    @staticmethod
    def test_float() -> None:
        assert KaggleNormalizer._safe_int(42.9, 0) == 42

    @staticmethod
    def test_string() -> None:
        assert KaggleNormalizer._safe_int("42", 0) == 42

    @staticmethod
    def test_none_returns_default() -> None:
        assert KaggleNormalizer._safe_int(None, -1) == -1

    @staticmethod
    def test_invalid_returns_default() -> None:
        assert KaggleNormalizer._safe_int("abc", 0) == 0

    @staticmethod
    def test_negative_returns_default() -> None:
        assert KaggleNormalizer._safe_int(-5, 0) == 0


class TestSafeIntNullable:
    @staticmethod
    def test_valid() -> None:
        assert KaggleNormalizer._safe_int_nullable(42) == 42

    @staticmethod
    def test_none() -> None:
        assert KaggleNormalizer._safe_int_nullable(None) is None

    @staticmethod
    def test_zero_returns_none() -> None:
        assert KaggleNormalizer._safe_int_nullable(0) is None

    @staticmethod
    def test_negative_returns_none() -> None:
        assert KaggleNormalizer._safe_int_nullable(-1) is None

    @staticmethod
    def test_invalid_returns_none() -> None:
        assert KaggleNormalizer._safe_int_nullable("abc") is None


class TestSafeFloat:
    @staticmethod
    def test_float() -> None:
        assert KaggleNormalizer._safe_float(7.5, 0.0) == 7.5

    @staticmethod
    def test_int() -> None:
        assert KaggleNormalizer._safe_float(7, 0.0) == 7.0

    @staticmethod
    def test_string() -> None:
        assert KaggleNormalizer._safe_float("7.5", 0.0) == 7.5

    @staticmethod
    def test_none_returns_default() -> None:
        assert KaggleNormalizer._safe_float(None, 0.0) == 0.0

    @staticmethod
    def test_invalid_returns_default() -> None:
        assert KaggleNormalizer._safe_float("abc", 0.0) == 0.0


# -------------------------------------------------------------------------
# String Cleaning
# -------------------------------------------------------------------------


class TestCleanString:
    @staticmethod
    def test_strips_whitespace() -> None:
        assert KaggleNormalizer._clean_string("  hello  ") == "hello"

    @staticmethod
    def test_none_returns_none() -> None:
        assert KaggleNormalizer._clean_string(None) is None

    @staticmethod
    def test_empty_returns_none() -> None:
        assert KaggleNormalizer._clean_string("  ") is None


class TestCleanText:
    @staticmethod
    def test_valid_text() -> None:
        assert KaggleNormalizer._clean_text("A valid overview text.") == "A valid overview text."

    @staticmethod
    def test_none_returns_none() -> None:
        assert KaggleNormalizer._clean_text(None) is None

    @staticmethod
    def test_short_returns_none() -> None:
        assert KaggleNormalizer._clean_text("Short") is None

    @staticmethod
    def test_placeholder_no_overview() -> None:
        assert KaggleNormalizer._clean_text("no overview") is None

    @staticmethod
    def test_placeholder_na() -> None:
        assert KaggleNormalizer._clean_text("N/A") is None

    @staticmethod
    def test_placeholder_no_description() -> None:
        assert KaggleNormalizer._clean_text("no description") is None


class TestCleanLanguage:
    @staticmethod
    def test_valid_code() -> None:
        assert KaggleNormalizer._clean_language("en") == "en"

    @staticmethod
    def test_uppercase_lowered() -> None:
        assert KaggleNormalizer._clean_language("EN") == "en"

    @staticmethod
    def test_none_returns_none() -> None:
        assert KaggleNormalizer._clean_language(None) is None

    @staticmethod
    def test_invalid_length_returns_none() -> None:
        assert KaggleNormalizer._clean_language("eng") is None

    @staticmethod
    def test_single_char_returns_none() -> None:
        assert KaggleNormalizer._clean_language("e") is None


# -------------------------------------------------------------------------
# Date Parsing
# -------------------------------------------------------------------------


class TestDateParsing:
    @staticmethod
    def test_prepare_date_string_valid() -> None:
        assert KaggleNormalizer._prepare_date_string("2024-01-15") == "2024-01-15"

    @staticmethod
    def test_prepare_date_string_none() -> None:
        assert KaggleNormalizer._prepare_date_string(None) is None

    @staticmethod
    def test_prepare_date_string_empty() -> None:
        assert KaggleNormalizer._prepare_date_string("  ") is None

    @staticmethod
    def test_try_parse_iso_date_valid() -> None:
        assert KaggleNormalizer._try_parse_iso_date("2024-01-15") == "2024-01-15"

    @staticmethod
    def test_try_parse_iso_date_invalid() -> None:
        assert KaggleNormalizer._try_parse_iso_date("not-a-date") is None

    @staticmethod
    def test_try_parse_year_only_valid() -> None:
        assert KaggleNormalizer._try_parse_year_only("2024") == "2024-01-01"

    @staticmethod
    def test_try_parse_year_only_too_low() -> None:
        assert KaggleNormalizer._try_parse_year_only("1899") is None

    @staticmethod
    def test_try_parse_year_only_too_high() -> None:
        assert KaggleNormalizer._try_parse_year_only("2101") is None

    @staticmethod
    def test_try_parse_year_only_invalid() -> None:
        assert KaggleNormalizer._try_parse_year_only("abc") is None


# -------------------------------------------------------------------------
# Statistics
# -------------------------------------------------------------------------


class TestStats:
    @staticmethod
    def test_initial_stats(normalizer: KaggleNormalizer) -> None:
        assert normalizer.get_stats() == {"normalized": 0, "skipped": 0}

    @staticmethod
    def test_stats_after_normalize(normalizer: KaggleNormalizer) -> None:
        normalizer.normalize(_make_raw())
        normalizer.normalize(_make_raw(id=None))
        stats = normalizer.get_stats()
        assert stats["normalized"] == 1
        assert stats["skipped"] == 1

    @staticmethod
    def test_reset_stats(normalizer: KaggleNormalizer) -> None:
        normalizer.normalize(_make_raw())
        normalizer.reset_stats()
        assert normalizer.get_stats() == {"normalized": 0, "skipped": 0}
