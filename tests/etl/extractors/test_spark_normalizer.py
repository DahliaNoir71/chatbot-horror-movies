"""Unit tests for Spark normalizer."""

import pytest

from src.etl.extractors.spark.normalizer import SparkNormalizer


@pytest.fixture()
def normalizer() -> SparkNormalizer:
    return SparkNormalizer()


def _make_raw(**overrides) -> dict:
    base = {
        "kaggle_id": 123,
        "title": "The Shining",
        "release_year": 1980,
        "decade": 1980,
        "rating": 8.4,
        "votes": 15000,
        "popularity": 45.6,
        "runtime": 146,
        "overview": "A family heads to an isolated hotel.",
        "genre_names": "Horror, Thriller",
        "rating_category": "excellent",
    }
    base.update(overrides)
    return base


# -------------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------------


class TestValidation:
    @staticmethod
    def test_valid_record(normalizer: SparkNormalizer) -> None:
        assert normalizer.normalize(_make_raw()) is not None

    @staticmethod
    def test_missing_kaggle_id(normalizer: SparkNormalizer) -> None:
        assert normalizer.normalize(_make_raw(kaggle_id=None)) is None

    @staticmethod
    def test_zero_kaggle_id(normalizer: SparkNormalizer) -> None:
        assert normalizer.normalize(_make_raw(kaggle_id=0)) is None

    @staticmethod
    def test_negative_kaggle_id(normalizer: SparkNormalizer) -> None:
        assert normalizer.normalize(_make_raw(kaggle_id=-1)) is None

    @staticmethod
    def test_missing_title(normalizer: SparkNormalizer) -> None:
        assert normalizer.normalize(_make_raw(title=None)) is None

    @staticmethod
    def test_empty_title(normalizer: SparkNormalizer) -> None:
        assert normalizer.normalize(_make_raw(title="  ")) is None

    @staticmethod
    def test_missing_rating(normalizer: SparkNormalizer) -> None:
        assert normalizer.normalize(_make_raw(rating=None)) is None

    @staticmethod
    def test_missing_votes(normalizer: SparkNormalizer) -> None:
        assert normalizer.normalize(_make_raw(votes=None)) is None


# -------------------------------------------------------------------------
# normalize()
# -------------------------------------------------------------------------


class TestNormalize:
    @staticmethod
    def test_basic_fields(normalizer: SparkNormalizer) -> None:
        result = normalizer.normalize(_make_raw())
        assert result["kaggle_id"] == 123
        assert result["title"] == "The Shining"
        assert result["source"] == "spark_kaggle"

    @staticmethod
    def test_numeric_fields(normalizer: SparkNormalizer) -> None:
        result = normalizer.normalize(_make_raw())
        assert result["rating"] == 8.4
        assert result["votes"] == 15000
        assert result["popularity"] == 45.6

    @staticmethod
    def test_release_year_and_decade(normalizer: SparkNormalizer) -> None:
        result = normalizer.normalize(_make_raw())
        assert result["release_year"] == 1980
        assert result["decade"] == 1980

    @staticmethod
    def test_none_release_year(normalizer: SparkNormalizer) -> None:
        result = normalizer.normalize(_make_raw(release_year=None))
        assert result["release_year"] is None

    @staticmethod
    def test_precomputed_rating_category(normalizer: SparkNormalizer) -> None:
        result = normalizer.normalize(_make_raw(rating_category="excellent"))
        assert result["rating_category"] == "excellent"

    @staticmethod
    def test_computed_rating_category(normalizer: SparkNormalizer) -> None:
        result = normalizer.normalize(_make_raw(rating_category=None))
        assert result["rating_category"] == "excellent"  # rating=8.4


# -------------------------------------------------------------------------
# normalize_batch()
# -------------------------------------------------------------------------


class TestNormalizeBatch:
    @staticmethod
    def test_batch(normalizer: SparkNormalizer) -> None:
        records = [_make_raw(kaggle_id=1), _make_raw(kaggle_id=2)]
        result = normalizer.normalize_batch(records)
        assert len(result) == 2

    @staticmethod
    def test_batch_skips_invalid(normalizer: SparkNormalizer) -> None:
        records = [_make_raw(kaggle_id=1), _make_raw(kaggle_id=None)]
        result = normalizer.normalize_batch(records)
        assert len(result) == 1

    @staticmethod
    def test_empty_batch(normalizer: SparkNormalizer) -> None:
        assert normalizer.normalize_batch([]) == []


# -------------------------------------------------------------------------
# Type Conversion Helpers
# -------------------------------------------------------------------------


class TestSafeFloat:
    @staticmethod
    def test_float() -> None:
        assert SparkNormalizer._safe_float(7.5) == 7.5

    @staticmethod
    def test_int() -> None:
        assert SparkNormalizer._safe_float(7) == 7.0

    @staticmethod
    def test_string() -> None:
        assert SparkNormalizer._safe_float("7.5") == 7.5

    @staticmethod
    def test_none_returns_zero() -> None:
        assert SparkNormalizer._safe_float(None) == 0.0

    @staticmethod
    def test_invalid_returns_zero() -> None:
        assert SparkNormalizer._safe_float("abc") == 0.0

    @staticmethod
    def test_rounds_to_2_decimals() -> None:
        result = SparkNormalizer._safe_float(7.555)
        assert round(result, 2) == result


class TestSafeInt:
    @staticmethod
    def test_int() -> None:
        assert SparkNormalizer._safe_int(42) == 42

    @staticmethod
    def test_float() -> None:
        assert SparkNormalizer._safe_int(42.9) == 42

    @staticmethod
    def test_string() -> None:
        assert SparkNormalizer._safe_int("42") == 42

    @staticmethod
    def test_none_returns_zero() -> None:
        assert SparkNormalizer._safe_int(None) == 0

    @staticmethod
    def test_invalid_returns_zero() -> None:
        assert SparkNormalizer._safe_int("abc") == 0


class TestSafeIntOrNone:
    @staticmethod
    def test_valid() -> None:
        assert SparkNormalizer._safe_int_or_none(42) == 42

    @staticmethod
    def test_none() -> None:
        assert SparkNormalizer._safe_int_or_none(None) is None

    @staticmethod
    def test_invalid() -> None:
        assert SparkNormalizer._safe_int_or_none("abc") is None


class TestSafeRuntime:
    @staticmethod
    def test_valid() -> None:
        assert SparkNormalizer._safe_runtime(120) == 120

    @staticmethod
    def test_none() -> None:
        assert SparkNormalizer._safe_runtime(None) is None

    @staticmethod
    def test_too_low() -> None:
        assert SparkNormalizer._safe_runtime(0) is None

    @staticmethod
    def test_too_high() -> None:
        assert SparkNormalizer._safe_runtime(601) is None

    @staticmethod
    def test_boundary_1() -> None:
        assert SparkNormalizer._safe_runtime(1) == 1

    @staticmethod
    def test_boundary_600() -> None:
        assert SparkNormalizer._safe_runtime(600) == 600

    @staticmethod
    def test_invalid() -> None:
        assert SparkNormalizer._safe_runtime("abc") is None


# -------------------------------------------------------------------------
# String Helpers
# -------------------------------------------------------------------------


class TestCleanTitle:
    @staticmethod
    def test_strips() -> None:
        assert SparkNormalizer._clean_title("  The Shining  ") == "The Shining"

    @staticmethod
    def test_none_returns_empty() -> None:
        assert SparkNormalizer._clean_title(None) == ""

    @staticmethod
    def test_empty_returns_empty() -> None:
        assert SparkNormalizer._clean_title("") == ""


class TestCleanText:
    @staticmethod
    def test_valid() -> None:
        assert SparkNormalizer._clean_text("Hello world") == "Hello world"

    @staticmethod
    def test_none() -> None:
        assert SparkNormalizer._clean_text(None) is None

    @staticmethod
    def test_empty() -> None:
        assert SparkNormalizer._clean_text("  ") is None


# -------------------------------------------------------------------------
# Rating Category
# -------------------------------------------------------------------------


class TestComputeRatingCategory:
    @staticmethod
    def test_excellent() -> None:
        assert SparkNormalizer._compute_rating_category(7.5) == "excellent"

    @staticmethod
    def test_excellent_boundary() -> None:
        assert SparkNormalizer._compute_rating_category(10.0) == "excellent"

    @staticmethod
    def test_good() -> None:
        assert SparkNormalizer._compute_rating_category(6.0) == "good"

    @staticmethod
    def test_good_upper() -> None:
        assert SparkNormalizer._compute_rating_category(7.4) == "good"

    @staticmethod
    def test_average() -> None:
        assert SparkNormalizer._compute_rating_category(4.0) == "average"

    @staticmethod
    def test_average_upper() -> None:
        assert SparkNormalizer._compute_rating_category(5.9) == "average"

    @staticmethod
    def test_poor() -> None:
        assert SparkNormalizer._compute_rating_category(3.9) == "poor"

    @staticmethod
    def test_poor_zero() -> None:
        assert SparkNormalizer._compute_rating_category(0.0) == "poor"


# -------------------------------------------------------------------------
# Statistics
# -------------------------------------------------------------------------


class TestStats:
    @staticmethod
    def test_initial(normalizer: SparkNormalizer) -> None:
        assert normalizer.get_stats() == {"normalized": 0, "skipped": 0}

    @staticmethod
    def test_after_normalize(normalizer: SparkNormalizer) -> None:
        normalizer.normalize(_make_raw())
        normalizer.normalize(_make_raw(kaggle_id=None))
        stats = normalizer.get_stats()
        assert stats["normalized"] == 1
        assert stats["skipped"] == 1

    @staticmethod
    def test_reset(normalizer: SparkNormalizer) -> None:
        normalizer.normalize(_make_raw())
        normalizer.reset_stats()
        assert normalizer.get_stats() == {"normalized": 0, "skipped": 0}
