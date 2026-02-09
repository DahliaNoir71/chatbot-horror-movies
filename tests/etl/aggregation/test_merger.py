"""Unit tests for multi-source data merger."""

import pytest

from src.etl.aggregation.merger import (
    SOURCE_IMDB,
    SOURCE_KAGGLE,
    SOURCE_RT,
    SOURCE_SPARK,
    SOURCE_TMDB,
    DataMerger,
    MergeStats,
    SourceIndex,
)
from src.etl.aggregation.schemas import AggregatedFilm


def _make_tmdb(**overrides) -> dict:
    base = {"tmdb_id": 1, "title": "The Shining", "vote_average": 8.4}
    base.update(overrides)
    return base


def _make_rt(**overrides) -> dict:
    base = {"tmdb_id": 1, "tomatometer_score": 85, "tomatometer_state": "certified_fresh"}
    base.update(overrides)
    return base


def _make_imdb(**overrides) -> dict:
    base = {"imdb_id": "tt0081505", "tmdb_id": 1, "title": "The Shining", "imdb_rating": 8.4, "imdb_votes": 1000000}
    base.update(overrides)
    return base


def _make_kaggle(**overrides) -> dict:
    base = {"tmdb_id": 1, "title": "The Shining", "rating": 7.5}
    base.update(overrides)
    return base


def _make_spark(**overrides) -> dict:
    base = {"tmdb_id": 1, "title": "The Shining", "rating": 7.0}
    base.update(overrides)
    return base


# -------------------------------------------------------------------------
# MergeStats
# -------------------------------------------------------------------------


class TestMergeStats:
    @staticmethod
    def test_default_values() -> None:
        stats = MergeStats()
        assert stats.total_tmdb == 0
        assert stats.merged_rt == 0

    @staticmethod
    def test_log_summary_no_error() -> None:
        stats = MergeStats(total_tmdb=10, merged_rt=5)
        stats.log_summary()


# -------------------------------------------------------------------------
# SourceIndex
# -------------------------------------------------------------------------


class TestSourceIndex:
    @staticmethod
    def test_add_by_tmdb_id() -> None:
        index = SourceIndex()
        index.add({"tmdb_id": 1, "score": 85})
        assert index.find(1, None) == {"tmdb_id": 1, "score": 85}

    @staticmethod
    def test_add_by_imdb_id() -> None:
        index = SourceIndex()
        index.add({"imdb_id": "tt1234567", "score": 85})
        assert index.find(None, "tt1234567") == {"imdb_id": "tt1234567", "score": 85}

    @staticmethod
    def test_tmdb_id_priority() -> None:
        index = SourceIndex()
        index.add({"tmdb_id": 1, "imdb_id": "tt1234567", "source": "a"})
        index.add({"imdb_id": "tt1234567", "source": "b"})
        result = index.find(1, "tt1234567")
        assert result["source"] == "a"

    @staticmethod
    def test_fallback_to_imdb_id() -> None:
        index = SourceIndex()
        index.add({"imdb_id": "tt1234567", "score": 90})
        result = index.find(999, "tt1234567")
        assert result["score"] == 90

    @staticmethod
    def test_not_found() -> None:
        index = SourceIndex()
        assert index.find(999, "tt9999999") is None

    @staticmethod
    def test_none_ids() -> None:
        index = SourceIndex()
        assert index.find(None, None) is None

    @staticmethod
    def test_add_without_ids() -> None:
        index = SourceIndex()
        index.add({"name": "test"})
        assert len(index.by_tmdb_id) == 0
        assert len(index.by_imdb_id) == 0


# -------------------------------------------------------------------------
# DataMerger - Basic
# -------------------------------------------------------------------------


class TestDataMergerBasic:
    @staticmethod
    def test_tmdb_only() -> None:
        merger = DataMerger()
        result = merger.merge([_make_tmdb()])
        assert len(result) == 1
        assert result[0].tmdb_id == 1
        assert result[0].title == "The Shining"
        assert SOURCE_TMDB in result[0].sources

    @staticmethod
    def test_empty_tmdb() -> None:
        merger = DataMerger()
        result = merger.merge([])
        assert result == []

    @staticmethod
    def test_invalid_tmdb_skipped() -> None:
        merger = DataMerger()
        result = merger.merge([{"invalid": "data"}])
        assert result == []
        assert merger.stats.failed_validations >= 1

    @staticmethod
    def test_multiple_films() -> None:
        merger = DataMerger()
        tmdb_films = [_make_tmdb(tmdb_id=1), _make_tmdb(tmdb_id=2, title="Alien")]
        result = merger.merge(tmdb_films)
        assert len(result) == 2
        assert merger.stats.total_tmdb == 2


# -------------------------------------------------------------------------
# DataMerger - RT Enrichment
# -------------------------------------------------------------------------


class TestDataMergerRT:
    @staticmethod
    def test_rt_enrichment_by_tmdb_id() -> None:
        merger = DataMerger()
        result = merger.merge([_make_tmdb()], rt_data=[_make_rt()])
        film = result[0]
        assert film.tomatometer_score == 85
        assert SOURCE_RT in film.sources
        assert merger.stats.merged_rt == 1

    @staticmethod
    def test_rt_no_match() -> None:
        merger = DataMerger()
        result = merger.merge([_make_tmdb()], rt_data=[_make_rt(tmdb_id=999)])
        assert result[0].tomatometer_score is None
        assert merger.stats.merged_rt == 0

    @staticmethod
    def test_rt_enrichment_fields() -> None:
        merger = DataMerger()
        rt = _make_rt(
            audience_score=75,
            critics_count=200,
            audience_count=5000,
            critics_consensus="A masterpiece.",
            rt_url="https://rottentomatoes.com/m/the_shining",
        )
        result = merger.merge([_make_tmdb()], rt_data=[rt])
        film = result[0]
        assert film.audience_score == 75
        assert film.critics_consensus == "A masterpiece."


# -------------------------------------------------------------------------
# DataMerger - IMDB Enrichment
# -------------------------------------------------------------------------


class TestDataMergerIMDB:
    @staticmethod
    def test_imdb_enrichment() -> None:
        merger = DataMerger()
        result = merger.merge([_make_tmdb()], imdb_data=[_make_imdb()])
        film = result[0]
        assert film.imdb_rating == pytest.approx(8.4)
        assert film.imdb_votes == 1000000
        assert SOURCE_IMDB in film.sources

    @staticmethod
    def test_imdb_fills_missing_imdb_id() -> None:
        merger = DataMerger()
        result = merger.merge(
            [_make_tmdb()],
            imdb_data=[_make_imdb()],
        )
        assert result[0].imdb_id == "tt0081505"

    @staticmethod
    def test_imdb_no_match() -> None:
        merger = DataMerger()
        result = merger.merge([_make_tmdb()], imdb_data=[_make_imdb(tmdb_id=999)])
        assert result[0].imdb_rating is None


# -------------------------------------------------------------------------
# DataMerger - Kaggle Enrichment
# -------------------------------------------------------------------------


class TestDataMergerKaggle:
    @staticmethod
    def test_kaggle_enrichment() -> None:
        merger = DataMerger()
        result = merger.merge([_make_tmdb()], kaggle_data=[_make_kaggle()])
        assert result[0].kaggle_rating == pytest.approx(7.5)
        assert SOURCE_KAGGLE in result[0].sources

    @staticmethod
    def test_kaggle_fills_missing_overview() -> None:
        merger = DataMerger()
        result = merger.merge(
            [_make_tmdb()],
            kaggle_data=[_make_kaggle(overview="Kaggle overview text")],
        )
        assert result[0].overview == "Kaggle overview text"

    @staticmethod
    def test_kaggle_does_not_overwrite_overview() -> None:
        merger = DataMerger()
        result = merger.merge(
            [_make_tmdb(overview="TMDB overview")],
            kaggle_data=[_make_kaggle(overview="Kaggle overview")],
        )
        assert result[0].overview == "TMDB overview"


# -------------------------------------------------------------------------
# DataMerger - Spark Enrichment
# -------------------------------------------------------------------------


class TestDataMergerSpark:
    @staticmethod
    def test_spark_enrichment() -> None:
        merger = DataMerger()
        result = merger.merge([_make_tmdb()], spark_data=[_make_spark()])
        assert result[0].spark_rating == pytest.approx(7.0)
        assert SOURCE_SPARK in result[0].sources

    @staticmethod
    def test_spark_no_match() -> None:
        merger = DataMerger()
        result = merger.merge([_make_tmdb()], spark_data=[_make_spark(tmdb_id=999)])
        assert result[0].spark_rating is None


# -------------------------------------------------------------------------
# DataMerger - Multi-source
# -------------------------------------------------------------------------


class TestDataMergerMultiSource:
    @staticmethod
    def test_all_sources() -> None:
        merger = DataMerger()
        result = merger.merge(
            [_make_tmdb()],
            rt_data=[_make_rt()],
            imdb_data=[_make_imdb()],
            kaggle_data=[_make_kaggle()],
            spark_data=[_make_spark()],
        )
        film = result[0]
        assert len(film.sources) == 5
        assert merger.stats.merged_rt == 1
        assert merger.stats.merged_imdb == 1
        assert merger.stats.merged_kaggle == 1
        assert merger.stats.merged_spark == 1

    @staticmethod
    def test_enrichment_count() -> None:
        merger = DataMerger()
        result = merger.merge(
            [_make_tmdb()],
            rt_data=[_make_rt()],
            imdb_data=[_make_imdb()],
        )
        assert result[0].enrichment_count == 3

    @staticmethod
    def test_none_enrichment_data() -> None:
        merger = DataMerger()
        result = merger.merge([_make_tmdb()], rt_data=None, imdb_data=None)
        assert len(result) == 1
        assert len(result[0].sources) == 1

    @staticmethod
    def test_stats_reset_between_merges() -> None:
        merger = DataMerger()
        merger.merge([_make_tmdb()], rt_data=[_make_rt()])
        merger.merge([_make_tmdb()])
        assert merger.stats.merged_rt == 0

    @staticmethod
    def test_imdb_fallback_by_imdb_id() -> None:
        merger = DataMerger()
        result = merger.merge(
            [_make_tmdb(imdb_id="tt0081505")],
            imdb_data=[_make_imdb(tmdb_id=None)],
        )
        assert result[0].imdb_rating == pytest.approx(8.4)
