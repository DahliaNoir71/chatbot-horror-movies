"""Unit tests for Rotten Tomatoes normalizer."""

import pytest

from src.etl.extractors.rotten_tomatoes.normalizer import RTNormalizer


@pytest.fixture()
def normalizer() -> RTNormalizer:
    return RTNormalizer()


def _make_raw(**overrides) -> dict:
    base = {
        "tomatometer_score": 85,
        "tomatometer_state": "certified_fresh",
        "critics_count": 200,
        "critics_average_rating": 7.5,
        "audience_score": 75,
        "audience_state": "upright",
        "audience_count": 5000,
        "audience_average_rating": 3.8,
        "critics_consensus": "A terrifying masterpiece that stands the test of time.",
        "rt_url": "https://rottentomatoes.com/m/the_shining",
        "rt_rating": "R",
    }
    base.update(overrides)
    return base


# -------------------------------------------------------------------------
# normalize()
# -------------------------------------------------------------------------


class TestNormalize:
    @staticmethod
    def test_basic(normalizer: RTNormalizer) -> None:
        result = normalizer.normalize(_make_raw(), film_id=1)
        assert result is not None
        assert result["film_id"] == 1
        assert result["tomatometer_score"] == 85
        assert result["audience_score"] == 75

    @staticmethod
    def test_empty_data_returns_none(normalizer: RTNormalizer) -> None:
        assert normalizer.normalize({}, film_id=1) is None

    @staticmethod
    def test_none_data_returns_none(normalizer: RTNormalizer) -> None:
        assert normalizer.normalize(None, film_id=1) is None

    @staticmethod
    def test_no_scores_returns_none(normalizer: RTNormalizer) -> None:
        raw = {"critics_count": 100, "rt_url": "https://example.com"}
        assert normalizer.normalize(raw, film_id=1) is None

    @staticmethod
    def test_tomatometer_only(normalizer: RTNormalizer) -> None:
        raw = {"tomatometer_score": 80}
        result = normalizer.normalize(raw, film_id=1)
        assert result is not None
        assert result["tomatometer_score"] == 80
        assert result["audience_score"] is None

    @staticmethod
    def test_audience_only(normalizer: RTNormalizer) -> None:
        raw = {"audience_score": 70}
        result = normalizer.normalize(raw, film_id=1)
        assert result is not None
        assert result["audience_score"] == 70
        assert result["tomatometer_score"] is None

    @staticmethod
    def test_state_normalized(normalizer: RTNormalizer) -> None:
        raw = _make_raw(tomatometer_state="certified-fresh", audience_state="spilled")
        result = normalizer.normalize(raw, film_id=1)
        assert result["tomatometer_state"] == "certified_fresh"
        assert result["audience_state"] == "rotten"

    @staticmethod
    def test_consensus_cleaned(normalizer: RTNormalizer) -> None:
        raw = _make_raw(critics_consensus="Critics Consensus: A brilliant film worth watching.")
        result = normalizer.normalize(raw, film_id=1)
        assert result["critics_consensus"] == "A brilliant film worth watching."


# -------------------------------------------------------------------------
# normalize_batch()
# -------------------------------------------------------------------------


class TestNormalizeBatch:
    @staticmethod
    def test_basic_batch(normalizer: RTNormalizer) -> None:
        results = [(1, _make_raw()), (2, _make_raw(tomatometer_score=50))]
        normalized = normalizer.normalize_batch(results)
        assert len(normalized) == 2

    @staticmethod
    def test_invalid_skipped(normalizer: RTNormalizer) -> None:
        results = [(1, _make_raw()), (2, {})]
        normalized = normalizer.normalize_batch(results)
        assert len(normalized) == 1

    @staticmethod
    def test_empty_batch(normalizer: RTNormalizer) -> None:
        assert normalizer.normalize_batch([]) == []


# -------------------------------------------------------------------------
# _safe_int()
# -------------------------------------------------------------------------


class TestSafeInt:
    @staticmethod
    def test_int_value() -> None:
        assert RTNormalizer._safe_int(85) == 85

    @staticmethod
    def test_float_value() -> None:
        assert RTNormalizer._safe_int(85.7) == 85

    @staticmethod
    def test_string_value() -> None:
        assert RTNormalizer._safe_int("85") == 85

    @staticmethod
    def test_none_returns_none() -> None:
        assert RTNormalizer._safe_int(None) is None

    @staticmethod
    def test_invalid_string_returns_none() -> None:
        assert RTNormalizer._safe_int("abc") is None

    @staticmethod
    def test_out_of_range_high() -> None:
        assert RTNormalizer._safe_int(101) is None

    @staticmethod
    def test_out_of_range_low() -> None:
        assert RTNormalizer._safe_int(-1) is None

    @staticmethod
    def test_boundary_0() -> None:
        assert RTNormalizer._safe_int(0) == 0

    @staticmethod
    def test_boundary_100() -> None:
        assert RTNormalizer._safe_int(100) == 100


# -------------------------------------------------------------------------
# _safe_float()
# -------------------------------------------------------------------------


class TestSafeFloat:
    @staticmethod
    def test_float_value() -> None:
        assert RTNormalizer._safe_float(7.5) == 7.5

    @staticmethod
    def test_int_value() -> None:
        assert RTNormalizer._safe_float(7) == 7.0

    @staticmethod
    def test_string_value() -> None:
        assert RTNormalizer._safe_float("7.5") == 7.5

    @staticmethod
    def test_none_returns_none() -> None:
        assert RTNormalizer._safe_float(None) is None

    @staticmethod
    def test_invalid_returns_none() -> None:
        assert RTNormalizer._safe_float("abc") is None


# -------------------------------------------------------------------------
# _normalize_state()
# -------------------------------------------------------------------------


class TestNormalizeState:
    @staticmethod
    def test_fresh() -> None:
        assert RTNormalizer._normalize_state("fresh") == "fresh"

    @staticmethod
    def test_certified_fresh_underscore() -> None:
        assert RTNormalizer._normalize_state("certified_fresh") == "certified_fresh"

    @staticmethod
    def test_certified_fresh_dash() -> None:
        assert RTNormalizer._normalize_state("certified-fresh") == "certified_fresh"

    @staticmethod
    def test_rotten() -> None:
        assert RTNormalizer._normalize_state("rotten") == "rotten"

    @staticmethod
    def test_positive_maps_to_fresh() -> None:
        assert RTNormalizer._normalize_state("positive") == "fresh"

    @staticmethod
    def test_negative_maps_to_rotten() -> None:
        assert RTNormalizer._normalize_state("negative") == "rotten"

    @staticmethod
    def test_upright_maps_to_fresh() -> None:
        assert RTNormalizer._normalize_state("upright") == "fresh"

    @staticmethod
    def test_spilled_maps_to_rotten() -> None:
        assert RTNormalizer._normalize_state("spilled") == "rotten"

    @staticmethod
    def test_none_returns_none() -> None:
        assert RTNormalizer._normalize_state(None) is None

    @staticmethod
    def test_empty_returns_none() -> None:
        assert RTNormalizer._normalize_state("") is None

    @staticmethod
    def test_case_insensitive() -> None:
        assert RTNormalizer._normalize_state("FRESH") == "fresh"

    @staticmethod
    def test_unknown_state_passthrough() -> None:
        assert RTNormalizer._normalize_state("unknown_state") == "unknown_state"


# -------------------------------------------------------------------------
# _clean_consensus()
# -------------------------------------------------------------------------


class TestCleanConsensus:
    @staticmethod
    def test_removes_critics_consensus_prefix() -> None:
        text = "Critics Consensus: A terrifying masterpiece."
        assert RTNormalizer._clean_consensus(text) == "A terrifying masterpiece."

    @staticmethod
    def test_removes_alternative_prefix() -> None:
        text = "Critic's Consensus: A terrifying masterpiece."
        assert RTNormalizer._clean_consensus(text) == "A terrifying masterpiece."

    @staticmethod
    def test_no_consensus_placeholder() -> None:
        assert RTNormalizer._clean_consensus("No consensus yet.") is None

    @staticmethod
    def test_short_text_returns_none() -> None:
        assert RTNormalizer._clean_consensus("Short text.") is None

    @staticmethod
    def test_none_returns_none() -> None:
        assert RTNormalizer._clean_consensus(None) is None

    @staticmethod
    def test_empty_returns_none() -> None:
        assert RTNormalizer._clean_consensus("") is None

    @staticmethod
    def test_valid_consensus_preserved() -> None:
        text = "A terrifying masterpiece that stands the test of time."
        assert RTNormalizer._clean_consensus(text) == text


# -------------------------------------------------------------------------
# Derived Properties
# -------------------------------------------------------------------------


class TestDerivedProperties:
    @staticmethod
    def test_is_certified_fresh_true() -> None:
        data = {"tomatometer_state": "certified_fresh"}
        assert RTNormalizer.is_certified_fresh(data) is True

    @staticmethod
    def test_is_certified_fresh_false() -> None:
        data = {"tomatometer_state": "fresh"}
        assert RTNormalizer.is_certified_fresh(data) is False

    @staticmethod
    def test_is_fresh_true() -> None:
        data = {"tomatometer_score": 60}
        assert RTNormalizer.is_fresh(data) is True

    @staticmethod
    def test_is_fresh_false() -> None:
        data = {"tomatometer_score": 59}
        assert RTNormalizer.is_fresh(data) is False

    @staticmethod
    def test_is_fresh_none_score() -> None:
        data = {"tomatometer_score": None}
        assert RTNormalizer.is_fresh(data) is False

    @staticmethod
    def test_is_rotten_true() -> None:
        data = {"tomatometer_score": 59}
        assert RTNormalizer.is_rotten(data) is True

    @staticmethod
    def test_is_rotten_false() -> None:
        data = {"tomatometer_score": 60}
        assert RTNormalizer.is_rotten(data) is False

    @staticmethod
    def test_is_rotten_none_score() -> None:
        data = {"tomatometer_score": None}
        assert RTNormalizer.is_rotten(data) is False
