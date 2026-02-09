"""Unit tests for main aggregator orchestrator."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.etl.aggregation.aggregator import (
    Aggregator,
    AggregationStats,
    DEFAULT_OUTPUT_FILENAME,
)
from src.etl.aggregation.schemas import AggregatedFilm


def _make_tmdb(**overrides) -> dict:
    base = {"tmdb_id": 1, "title": "The Shining", "vote_average": 8.4}
    base.update(overrides)
    return base


# -------------------------------------------------------------------------
# AggregationStats
# -------------------------------------------------------------------------


class TestAggregationStats:
    @staticmethod
    def test_defaults() -> None:
        stats = AggregationStats()
        assert stats.input_tmdb == 0
        assert stats.final_count == 0

    @staticmethod
    def test_duration_seconds() -> None:
        stats = AggregationStats(
            start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 1, 0, 0, 10, tzinfo=UTC),
        )
        assert stats.duration_seconds == 10.0

    @staticmethod
    def test_duration_no_times() -> None:
        assert AggregationStats().duration_seconds == 0.0

    @staticmethod
    def test_to_dict() -> None:
        stats = AggregationStats(input_tmdb=100, after_merge=95, final_count=90)
        d = stats.to_dict()
        assert d["input"]["tmdb"] == 100
        assert d["pipeline"]["after_merge"] == 95
        assert d["pipeline"]["final_count"] == 90

    @staticmethod
    def test_log_summary_no_error() -> None:
        stats = AggregationStats(
            start_time=datetime(2024, 1, 1, tzinfo=UTC),
            end_time=datetime(2024, 1, 1, 0, 0, 5, tzinfo=UTC),
            final_count=100,
        )
        stats.log_summary()


# -------------------------------------------------------------------------
# Aggregator
# -------------------------------------------------------------------------


class TestAggregator:
    @staticmethod
    def test_aggregate_tmdb_only() -> None:
        agg = Aggregator()
        result = agg.aggregate([_make_tmdb()])
        assert len(result) == 1
        assert isinstance(result[0], AggregatedFilm)
        assert result[0].aggregated_score > 0

    @staticmethod
    def test_aggregate_empty() -> None:
        agg = Aggregator()
        result = agg.aggregate([])
        assert result == []

    @staticmethod
    def test_aggregate_with_enrichments() -> None:
        agg = Aggregator()
        rt = [{"tmdb_id": 1, "tomatometer_score": 85}]
        imdb = [{"tmdb_id": 1, "imdb_id": "tt1234567", "title": "The Shining", "imdb_rating": 8.0}]
        result = agg.aggregate([_make_tmdb()], rt_data=rt, imdb_data=imdb)
        assert len(result) == 1
        assert result[0].tomatometer_score == 85

    @staticmethod
    def test_deduplication_in_pipeline() -> None:
        agg = Aggregator()
        films = [_make_tmdb(tmdb_id=1), _make_tmdb(tmdb_id=1)]
        result = agg.aggregate(films)
        assert len(result) == 1

    @staticmethod
    def test_stats_recorded() -> None:
        agg = Aggregator()
        agg.aggregate([_make_tmdb()])
        assert agg.stats.input_tmdb == 1
        assert agg.stats.final_count == 1
        assert agg.stats.start_time is not None
        assert agg.stats.end_time is not None

    @staticmethod
    def test_to_dicts() -> None:
        agg = Aggregator()
        films = agg.aggregate([_make_tmdb()])
        dicts = agg.to_dicts(films)
        assert len(dicts) == 1
        assert dicts[0]["tmdb_id"] == 1

    @staticmethod
    def test_export_json(tmp_path: Path) -> None:
        agg = Aggregator()
        films = agg.aggregate([_make_tmdb()])
        output = tmp_path / "output.json"
        result = agg.export_json(films, output_path=output)
        assert result.exists()
        assert result == output

    @staticmethod
    def test_export_json_default_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        agg = Aggregator()
        films = agg.aggregate([_make_tmdb()])
        result = agg.export_json(films)
        assert result.name == DEFAULT_OUTPUT_FILENAME

    @staticmethod
    def test_export_json_without_stats(tmp_path: Path) -> None:
        agg = Aggregator()
        films = agg.aggregate([_make_tmdb()])
        output = tmp_path / "no_stats.json"
        agg.export_json(films, output_path=output, include_stats=False)
        import json

        with open(output) as f:
            data = json.load(f)
        assert "stats" not in data

    @staticmethod
    def test_film_to_dict_date_serialization() -> None:
        from datetime import date

        film = AggregatedFilm(tmdb_id=1, title="Test", release_date=date(2024, 1, 15))
        result = Aggregator._film_to_dict(film)
        assert result["release_date"] == "2024-01-15"

    @staticmethod
    def test_film_to_dict_no_date() -> None:
        film = AggregatedFilm(tmdb_id=1, title="Test")
        result = Aggregator._film_to_dict(film)
        assert result["release_date"] is None
