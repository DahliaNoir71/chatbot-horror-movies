"""Unit tests for film deduplicator."""

from datetime import date

import pytest

from src.etl.aggregation.deduplicator import (
    SIMILARITY_THRESHOLD,
    YEAR_TOLERANCE,
    Deduplicator,
    DeduplicationStats,
    SeenFilmsTracker,
)
from src.etl.aggregation.schemas import AggregatedFilm


def _make_film(**overrides) -> AggregatedFilm:
    base = {"tmdb_id": 1, "title": "Test Film"}
    base.update(overrides)
    return AggregatedFilm(**base)


# -------------------------------------------------------------------------
# DeduplicationStats
# -------------------------------------------------------------------------


class TestDeduplicationStats:
    @staticmethod
    def test_default_values() -> None:
        stats = DeduplicationStats()
        assert stats.total_input == 0
        assert stats.total_duplicates == 0

    @staticmethod
    def test_total_duplicates() -> None:
        stats = DeduplicationStats(
            duplicates_tmdb_id=2,
            duplicates_imdb_id=1,
            duplicates_fuzzy=3,
        )
        assert stats.total_duplicates == 6

    @staticmethod
    def test_log_summary_no_error() -> None:
        stats = DeduplicationStats(total_input=10, total_output=8)
        stats.log_summary()


# -------------------------------------------------------------------------
# SeenFilmsTracker
# -------------------------------------------------------------------------


class TestSeenFilmsTracker:
    @staticmethod
    def test_add_and_has_tmdb_id() -> None:
        tracker = SeenFilmsTracker()
        film = _make_film(tmdb_id=123)
        tracker.add(film)
        assert tracker.has_tmdb_id(123) is True
        assert tracker.has_tmdb_id(999) is False

    @staticmethod
    def test_add_and_has_imdb_id() -> None:
        tracker = SeenFilmsTracker()
        film = _make_film(imdb_id="tt1234567")
        tracker.add(film)
        assert tracker.has_imdb_id("tt1234567") is True
        assert tracker.has_imdb_id("tt9999999") is False

    @staticmethod
    def test_has_imdb_id_none() -> None:
        tracker = SeenFilmsTracker()
        assert tracker.has_imdb_id(None) is False

    @staticmethod
    def test_has_imdb_id_empty() -> None:
        tracker = SeenFilmsTracker()
        assert tracker.has_imdb_id("") is False

    @staticmethod
    def test_title_year_tracking() -> None:
        tracker = SeenFilmsTracker()
        film = _make_film(release_date=date(2024, 1, 1))
        tracker.add(film)
        assert len(tracker.by_title_year) == 1

    @staticmethod
    def test_find_similar_title_exact_match() -> None:
        tracker = SeenFilmsTracker()
        film = _make_film(title="The Shining", release_date=date(1980, 5, 23))
        tracker.add(film)
        result = tracker.find_similar_title("The Shining", 1980)
        assert result is not None

    @staticmethod
    def test_find_similar_title_fuzzy_match() -> None:
        tracker = SeenFilmsTracker()
        film = _make_film(title="The Shining", release_date=date(1980, 5, 23))
        tracker.add(film)
        result = tracker.find_similar_title("The Shinning", 1980)
        assert result is not None

    @staticmethod
    def test_find_similar_title_no_match() -> None:
        tracker = SeenFilmsTracker()
        film = _make_film(title="The Shining", release_date=date(1980, 5, 23))
        tracker.add(film)
        result = tracker.find_similar_title("Alien", 1979)
        assert result is None

    @staticmethod
    def test_find_similar_title_no_year() -> None:
        tracker = SeenFilmsTracker()
        result = tracker.find_similar_title("Any Title", None)
        assert result is None

    @staticmethod
    def test_year_tolerance() -> None:
        tracker = SeenFilmsTracker()
        film = _make_film(title="The Shining", release_date=date(1980, 5, 23))
        tracker.add(film)
        assert tracker.find_similar_title("The Shining", 1981) is not None
        assert tracker.find_similar_title("The Shining", 1979) is not None

    @staticmethod
    def test_year_out_of_tolerance() -> None:
        tracker = SeenFilmsTracker()
        film = _make_film(title="The Shining", release_date=date(1980, 5, 23))
        tracker.add(film)
        assert tracker.find_similar_title("The Shining", 1978) is None

    @staticmethod
    def test_normalize_title() -> None:
        assert SeenFilmsTracker._normalize_title("  The Shining  ") == "the shining"

    @staticmethod
    def test_is_year_match_within_tolerance() -> None:
        assert SeenFilmsTracker._is_year_match(2024, 2024) is True
        assert SeenFilmsTracker._is_year_match(2024, 2025) is True
        assert SeenFilmsTracker._is_year_match(2024, 2023) is True

    @staticmethod
    def test_is_year_match_out_of_tolerance() -> None:
        assert SeenFilmsTracker._is_year_match(2024, 2026) is False

    @staticmethod
    def test_is_title_similar_true() -> None:
        assert SeenFilmsTracker._is_title_similar("the shining", "the shining") is True

    @staticmethod
    def test_is_title_similar_false() -> None:
        assert SeenFilmsTracker._is_title_similar("alien", "the shining") is False


# -------------------------------------------------------------------------
# Deduplicator
# -------------------------------------------------------------------------


class TestDeduplicator:
    @staticmethod
    def test_no_duplicates() -> None:
        dedup = Deduplicator()
        films = [_make_film(tmdb_id=1), _make_film(tmdb_id=2)]
        result = dedup.deduplicate(films)
        assert len(result) == 2

    @staticmethod
    def test_tmdb_id_duplicate() -> None:
        dedup = Deduplicator()
        films = [_make_film(tmdb_id=1), _make_film(tmdb_id=1)]
        result = dedup.deduplicate(films)
        assert len(result) == 1
        assert dedup.stats.duplicates_tmdb_id == 1

    @staticmethod
    def test_imdb_id_duplicate() -> None:
        dedup = Deduplicator()
        films = [
            _make_film(tmdb_id=1, imdb_id="tt1234567"),
            _make_film(tmdb_id=2, imdb_id="tt1234567"),
        ]
        result = dedup.deduplicate(films)
        assert len(result) == 1
        assert dedup.stats.duplicates_imdb_id == 1

    @staticmethod
    def test_fuzzy_title_duplicate() -> None:
        dedup = Deduplicator()
        films = [
            _make_film(tmdb_id=1, title="The Shining", release_date=date(1980, 5, 23)),
            _make_film(tmdb_id=2, title="The Shinning", release_date=date(1980, 6, 1)),
        ]
        result = dedup.deduplicate(films)
        assert len(result) == 1
        assert dedup.stats.duplicates_fuzzy == 1

    @staticmethod
    def test_different_titles_not_duplicate() -> None:
        dedup = Deduplicator()
        films = [
            _make_film(tmdb_id=1, title="The Shining", release_date=date(1980, 5, 23)),
            _make_film(tmdb_id=2, title="Alien", release_date=date(1979, 6, 22)),
        ]
        result = dedup.deduplicate(films)
        assert len(result) == 2

    @staticmethod
    def test_empty_list() -> None:
        dedup = Deduplicator()
        assert dedup.deduplicate([]) == []

    @staticmethod
    def test_stats_counts() -> None:
        dedup = Deduplicator()
        films = [_make_film(tmdb_id=1), _make_film(tmdb_id=1), _make_film(tmdb_id=2)]
        result = dedup.deduplicate(films)
        assert dedup.stats.total_input == 3
        assert dedup.stats.total_output == 2
        assert dedup.stats.total_duplicates == 1

    @staticmethod
    def test_stats_reset_between_calls() -> None:
        dedup = Deduplicator()
        dedup.deduplicate([_make_film(tmdb_id=1), _make_film(tmdb_id=1)])
        dedup.deduplicate([_make_film(tmdb_id=1)])
        assert dedup.stats.total_input == 1
        assert dedup.stats.duplicates_tmdb_id == 0
