"""Unit tests for aggregated score calculator."""

from datetime import date

import pytest
from pytest import approx

from src.etl.aggregation.schemas import AggregatedFilm
from src.etl.aggregation.score_calculator import (
    MAX_SCORE,
    RT_SCALE_FACTOR,
    WEIGHT_IMDB,
    WEIGHT_KAGGLE,
    WEIGHT_RT,
    WEIGHT_TMDB,
    ScoreCalculator,
    ScoreComponent,
    ScoreExtractor,
    ScoreStats,
)


def _make_film(**overrides) -> AggregatedFilm:
    base = {"tmdb_id": 1, "title": "Test Film"}
    base.update(overrides)
    return AggregatedFilm(**base)


# -------------------------------------------------------------------------
# ScoreStats
# -------------------------------------------------------------------------


class TestScoreStats:
    @staticmethod
    def test_default_values() -> None:
        stats = ScoreStats()
        assert stats.total_films == 0
        assert stats.with_tmdb == 0
        assert stats.score_sum == 0.0

    @staticmethod
    def test_avg_score_zero_films() -> None:
        stats = ScoreStats()
        assert stats.avg_score == 0.0

    @staticmethod
    def test_avg_score_calculation() -> None:
        stats = ScoreStats(total_films=2, score_sum=15.0)
        assert stats.avg_score == approx(7.5)

    @staticmethod
    def test_log_summary_no_error() -> None:
        stats = ScoreStats(total_films=10, score_sum=70.0)
        stats.log_summary()


# -------------------------------------------------------------------------
# ScoreComponent
# -------------------------------------------------------------------------


class TestScoreComponent:
    @staticmethod
    def test_weighted_value() -> None:
        c = ScoreComponent(value=8.0, weight=0.25)
        assert c.weighted_value == approx(2.0)

    @staticmethod
    def test_zero_weight() -> None:
        c = ScoreComponent(value=8.0, weight=0.0)
        assert c.weighted_value == approx(0.0)


# -------------------------------------------------------------------------
# ScoreExtractor
# -------------------------------------------------------------------------


class TestScoreExtractor:
    @staticmethod
    def test_tmdb_score() -> None:
        film = _make_film(vote_average=7.5)
        result = ScoreExtractor.get_tmdb_score(film)
        assert result is not None
        assert result.value == approx(7.5)
        assert result.weight == WEIGHT_TMDB

    @staticmethod
    def test_tmdb_score_zero_returns_none() -> None:
        film = _make_film(vote_average=0.0)
        assert ScoreExtractor.get_tmdb_score(film) is None

    @staticmethod
    def test_rt_score() -> None:
        film = _make_film(tomatometer_score=85)
        result = ScoreExtractor.get_rt_score(film)
        assert result is not None
        assert result.value == approx(85 / RT_SCALE_FACTOR)
        assert result.weight == WEIGHT_RT

    @staticmethod
    def test_rt_score_none_returns_none() -> None:
        film = _make_film()
        assert ScoreExtractor.get_rt_score(film) is None

    @staticmethod
    def test_imdb_score() -> None:
        film = _make_film(imdb_rating=8.0)
        result = ScoreExtractor.get_imdb_score(film)
        assert result is not None
        assert result.value == approx(8.0)
        assert result.weight == WEIGHT_IMDB

    @staticmethod
    def test_imdb_score_none_returns_none() -> None:
        film = _make_film()
        assert ScoreExtractor.get_imdb_score(film) is None

    @staticmethod
    def test_kaggle_score() -> None:
        film = _make_film(kaggle_rating=7.0)
        result = ScoreExtractor.get_kaggle_score(film)
        assert result is not None
        assert result.value == approx(7.0)
        assert result.weight == WEIGHT_KAGGLE

    @staticmethod
    def test_kaggle_score_none_returns_none() -> None:
        film = _make_film()
        assert ScoreExtractor.get_kaggle_score(film) is None


# -------------------------------------------------------------------------
# ScoreCalculator
# -------------------------------------------------------------------------


class TestScoreCalculator:
    @staticmethod
    def test_single_source_tmdb() -> None:
        calc = ScoreCalculator()
        films = [_make_film(vote_average=8.0)]
        result = calc.calculate_scores(films)
        assert result[0].aggregated_score == approx(8.0)

    @staticmethod
    def test_two_sources_tmdb_imdb() -> None:
        calc = ScoreCalculator()
        films = [_make_film(vote_average=8.0, imdb_rating=7.0)]
        result = calc.calculate_scores(films)
        expected = (8.0 * WEIGHT_TMDB + 7.0 * WEIGHT_IMDB) / (WEIGHT_TMDB + WEIGHT_IMDB)
        assert result[0].aggregated_score == approx(expected, abs=0.01)

    @staticmethod
    def test_all_sources() -> None:
        calc = ScoreCalculator()
        films = [
            _make_film(
                vote_average=8.0,
                tomatometer_score=85,
                imdb_rating=7.5,
                kaggle_rating=7.0,
            )
        ]
        result = calc.calculate_scores(films)
        assert 0 < result[0].aggregated_score <= MAX_SCORE

    @staticmethod
    def test_no_scores_returns_zero() -> None:
        calc = ScoreCalculator()
        films = [_make_film(vote_average=0.0)]
        result = calc.calculate_scores(films)
        assert result[0].aggregated_score == approx(0.0)

    @staticmethod
    def test_multiple_films() -> None:
        calc = ScoreCalculator()
        films = [
            _make_film(tmdb_id=1, vote_average=8.0),
            _make_film(tmdb_id=2, vote_average=6.0),
        ]
        result = calc.calculate_scores(films)
        assert len(result) == 2
        assert result[0].aggregated_score > result[1].aggregated_score

    @staticmethod
    def test_stats_updated() -> None:
        calc = ScoreCalculator()
        films = [_make_film(vote_average=8.0, tomatometer_score=90, imdb_rating=7.5)]
        calc.calculate_scores(films)
        assert calc.stats.total_films == 1
        assert calc.stats.with_tmdb == 1
        assert calc.stats.with_rt == 1
        assert calc.stats.with_imdb == 1

    @staticmethod
    def test_stats_reset_between_calls() -> None:
        calc = ScoreCalculator()
        calc.calculate_scores([_make_film(vote_average=8.0)])
        calc.calculate_scores([_make_film(vote_average=6.0)])
        assert calc.stats.total_films == 1

    @staticmethod
    def test_empty_list() -> None:
        calc = ScoreCalculator()
        result = calc.calculate_scores([])
        assert result == []

    @staticmethod
    def test_score_capped_at_max() -> None:
        components = [ScoreComponent(value=10.0, weight=1.0)]
        result = ScoreCalculator._compute_weighted_average(components)
        assert result <= MAX_SCORE

    @staticmethod
    def test_weighted_average_normalization() -> None:
        components = [
            ScoreComponent(value=8.0, weight=0.3),
            ScoreComponent(value=6.0, weight=0.3),
        ]
        result = ScoreCalculator._compute_weighted_average(components)
        assert result == approx(7.0)
