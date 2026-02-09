"""Unit tests for IMDB SQLite normalizer."""

import pytest

from src.etl.extractors.sqlite.normalizer import IMDBNormalizer


@pytest.fixture()
def normalizer() -> IMDBNormalizer:
    return IMDBNormalizer()


def _make_raw(**overrides) -> dict:
    base = {
        "imdb_id": "tt0081505",
        "title": "The Shining",
        "original_title": "The Shining",
        "year": 1980,
        "runtime": 146,
        "genres": "Horror, Drama",
        "rating": 8.4,
        "votes": 1000000,
        "directors": "nm0000040",
        "writers": "nm0000040,nm0000175",
    }
    base.update(overrides)
    return base


# -------------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------------


class TestValidation:
    @staticmethod
    def test_valid_record(normalizer: IMDBNormalizer) -> None:
        assert normalizer.normalize(_make_raw()) is not None

    @staticmethod
    def test_missing_imdb_id(normalizer: IMDBNormalizer) -> None:
        assert normalizer.normalize(_make_raw(imdb_id=None)) is None

    @staticmethod
    def test_empty_imdb_id(normalizer: IMDBNormalizer) -> None:
        assert normalizer.normalize(_make_raw(imdb_id="")) is None

    @staticmethod
    def test_invalid_imdb_id_no_tt(normalizer: IMDBNormalizer) -> None:
        assert normalizer.normalize(_make_raw(imdb_id="nm1234567")) is None

    @staticmethod
    def test_invalid_imdb_id_no_digits(normalizer: IMDBNormalizer) -> None:
        assert normalizer.normalize(_make_raw(imdb_id="ttabcdef")) is None

    @staticmethod
    def test_valid_7_digit_imdb_id(normalizer: IMDBNormalizer) -> None:
        assert normalizer.normalize(_make_raw(imdb_id="tt1234567")) is not None

    @staticmethod
    def test_valid_8_digit_imdb_id(normalizer: IMDBNormalizer) -> None:
        assert normalizer.normalize(_make_raw(imdb_id="tt12345678")) is not None

    @staticmethod
    def test_missing_rating(normalizer: IMDBNormalizer) -> None:
        assert normalizer.normalize(_make_raw(rating=None)) is None

    @staticmethod
    def test_missing_votes(normalizer: IMDBNormalizer) -> None:
        assert normalizer.normalize(_make_raw(votes=None)) is None


# -------------------------------------------------------------------------
# normalize()
# -------------------------------------------------------------------------


class TestNormalize:
    @staticmethod
    def test_basic_fields(normalizer: IMDBNormalizer) -> None:
        result = normalizer.normalize(_make_raw())
        assert result["imdb_id"] == "tt0081505"
        assert result["imdb_rating"] == 8.4
        assert result["imdb_votes"] == 1000000

    @staticmethod
    def test_runtime_valid(normalizer: IMDBNormalizer) -> None:
        result = normalizer.normalize(_make_raw(runtime=120))
        assert result["runtime"] == 120

    @staticmethod
    def test_runtime_none(normalizer: IMDBNormalizer) -> None:
        result = normalizer.normalize(_make_raw(runtime=None))
        assert result["runtime"] is None

    @staticmethod
    def test_runtime_out_of_range(normalizer: IMDBNormalizer) -> None:
        result = normalizer.normalize(_make_raw(runtime=601))
        assert result["runtime"] is None

    @staticmethod
    def test_runtime_zero(normalizer: IMDBNormalizer) -> None:
        result = normalizer.normalize(_make_raw(runtime=0))
        assert result["runtime"] is None


# -------------------------------------------------------------------------
# normalize_batch()
# -------------------------------------------------------------------------


class TestNormalizeBatch:
    @staticmethod
    def test_batch(normalizer: IMDBNormalizer) -> None:
        records = [_make_raw(imdb_id="tt0000001"), _make_raw(imdb_id="tt0000002")]
        result = normalizer.normalize_batch(records)
        assert len(result) == 2

    @staticmethod
    def test_batch_skips_invalid(normalizer: IMDBNormalizer) -> None:
        records = [_make_raw(), _make_raw(imdb_id=None)]
        result = normalizer.normalize_batch(records)
        assert len(result) == 1

    @staticmethod
    def test_empty_batch(normalizer: IMDBNormalizer) -> None:
        assert normalizer.normalize_batch([]) == []


# -------------------------------------------------------------------------
# IMDB ID Validation
# -------------------------------------------------------------------------


class TestIMDBIDValidation:
    @staticmethod
    def test_valid_format() -> None:
        assert IMDBNormalizer._is_valid_imdb_id("tt0081505") is True

    @staticmethod
    def test_wrong_prefix() -> None:
        assert IMDBNormalizer._is_valid_imdb_id("nm0081505") is False

    @staticmethod
    def test_no_digits() -> None:
        assert IMDBNormalizer._is_valid_imdb_id("ttabcdefg") is False

    @staticmethod
    def test_mixed() -> None:
        assert IMDBNormalizer._is_valid_imdb_id("tt123abc") is False

    @staticmethod
    def test_short_id() -> None:
        assert IMDBNormalizer._is_valid_imdb_id("tt12") is True

    @staticmethod
    def test_just_tt() -> None:
        assert IMDBNormalizer._is_valid_imdb_id("tt") is False


# -------------------------------------------------------------------------
# Type Conversion Helpers
# -------------------------------------------------------------------------


class TestSafeFloat:
    @staticmethod
    def test_float() -> None:
        assert IMDBNormalizer._safe_float(8.4) == 8.4

    @staticmethod
    def test_int() -> None:
        assert IMDBNormalizer._safe_float(8) == 8.0

    @staticmethod
    def test_string() -> None:
        assert IMDBNormalizer._safe_float("8.4") == 8.4

    @staticmethod
    def test_none() -> None:
        assert IMDBNormalizer._safe_float(None) == 0.0

    @staticmethod
    def test_invalid() -> None:
        assert IMDBNormalizer._safe_float("abc") == 0.0

    @staticmethod
    def test_rounds_to_1_decimal() -> None:
        assert IMDBNormalizer._safe_float(8.45) == 8.4


class TestSafeInt:
    @staticmethod
    def test_int() -> None:
        assert IMDBNormalizer._safe_int(42) == 42

    @staticmethod
    def test_float() -> None:
        assert IMDBNormalizer._safe_int(42.9) == 42

    @staticmethod
    def test_none() -> None:
        assert IMDBNormalizer._safe_int(None) == 0

    @staticmethod
    def test_invalid() -> None:
        assert IMDBNormalizer._safe_int("abc") == 0


class TestSafeRuntime:
    @staticmethod
    def test_valid() -> None:
        assert IMDBNormalizer._safe_runtime(120) == 120

    @staticmethod
    def test_none() -> None:
        assert IMDBNormalizer._safe_runtime(None) is None

    @staticmethod
    def test_zero() -> None:
        assert IMDBNormalizer._safe_runtime(0) is None

    @staticmethod
    def test_over_600() -> None:
        assert IMDBNormalizer._safe_runtime(601) is None

    @staticmethod
    def test_boundary_1() -> None:
        assert IMDBNormalizer._safe_runtime(1) == 1

    @staticmethod
    def test_boundary_600() -> None:
        assert IMDBNormalizer._safe_runtime(600) == 600

    @staticmethod
    def test_invalid() -> None:
        assert IMDBNormalizer._safe_runtime("abc") is None


# -------------------------------------------------------------------------
# Statistics
# -------------------------------------------------------------------------


class TestStats:
    @staticmethod
    def test_initial(normalizer: IMDBNormalizer) -> None:
        assert normalizer.get_stats() == {"normalized": 0, "skipped": 0}

    @staticmethod
    def test_counts(normalizer: IMDBNormalizer) -> None:
        normalizer.normalize(_make_raw())
        normalizer.normalize(_make_raw(imdb_id=None))
        stats = normalizer.get_stats()
        assert stats["normalized"] == 1
        assert stats["skipped"] == 1

    @staticmethod
    def test_reset(normalizer: IMDBNormalizer) -> None:
        normalizer.normalize(_make_raw())
        normalizer.reset_stats()
        assert normalizer.get_stats() == {"normalized": 0, "skipped": 0}
