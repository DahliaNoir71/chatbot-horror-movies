"""Unit tests for RAGImporter document preparation.

Covers the pure helpers that build the vectorized content and
the JSONB metadata — the two parts that drive retrieval quality
and frontend filtering.
"""

from __future__ import annotations

from typing import Any

from src.database.importer.rag_importer import (
    CONTENT_CAST_LIMIT,
    CONTENT_KEYWORDS_LIMIT,
    METADATA_CAST_LIMIT,
    RAGImporter,
)


def _make_film(**overrides: Any) -> dict[str, Any]:
    """Build a minimal film dict with sensible horror defaults."""
    base: dict[str, Any] = {
        "tmdb_id": 948,
        "title": "Halloween",
        "release_date": "1978-10-25",
        "overview": "Michael Myers escapes to stalk babysitters.",
        "tagline": "The night HE came home.",
        "genres": ["Horror", "Thriller"],
        "keywords": ["slasher", "masked killer", "babysitter"],
        "cast": ["Jamie Lee Curtis", "Donald Pleasence", "P. J. Soles"],
        "director": "John Carpenter",
        "writers": ["John Carpenter", "Debra Hill"],
        "runtime": 91,
        "vote_average": 7.7,
        "tomatometer_score": 96,
        "tomatometer_state": "certified_fresh",
        "imdb_rating": 7.7,
        "aggregated_score": 8.4,
        "critics_consensus": "Scary, suspenseful, and stylish.",
    }
    base.update(overrides)
    return base


class TestBuildHeader:
    """RAGImporter._build_header — shared content prefix."""

    @staticmethod
    def test_header_contains_all_fields_when_present() -> None:
        film = _make_film()
        header = RAGImporter._build_header(film)
        assert "Halloween (1978) - Genres: Horror, Thriller" in header
        assert "Keywords: slasher, masked killer, babysitter" in header
        assert "Director: John Carpenter" in header
        assert "Cast: Jamie Lee Curtis, Donald Pleasence, P. J. Soles" in header

    @staticmethod
    def test_header_skips_empty_sections() -> None:
        film = _make_film(keywords=[], cast=[], director=None)
        header = RAGImporter._build_header(film)
        assert "Keywords:" not in header
        assert "Director:" not in header
        assert "Cast:" not in header
        assert "Halloween (1978)" in header

    @staticmethod
    def test_header_missing_release_date() -> None:
        film = _make_film(release_date=None)
        header = RAGImporter._build_header(film)
        assert "Halloween ()" in header

    @staticmethod
    def test_header_truncates_cast_and_keywords() -> None:
        film = _make_film(
            cast=[f"Actor{i}" for i in range(CONTENT_CAST_LIMIT + 3)],
            keywords=[f"kw{i}" for i in range(CONTENT_KEYWORDS_LIMIT + 5)],
        )
        header = RAGImporter._build_header(film)
        assert f"Actor{CONTENT_CAST_LIMIT - 1}" in header
        assert f"Actor{CONTENT_CAST_LIMIT}" not in header
        assert f"kw{CONTENT_KEYWORDS_LIMIT - 1}" in header
        assert f"kw{CONTENT_KEYWORDS_LIMIT}" not in header


class TestCreateOverviewDoc:
    """RAGImporter._create_overview_doc — film overview embedding."""

    @staticmethod
    def test_overview_doc_includes_header_and_overview_and_tagline() -> None:
        film = _make_film()
        doc = RAGImporter._create_overview_doc(film, tmdb_id=948, metadata={})
        assert doc is not None
        assert doc.source_type == "film_overview"
        assert doc.source_id == 948
        assert "Director: John Carpenter" in doc.content
        assert "Michael Myers escapes" in doc.content
        assert "Tagline: The night HE came home." in doc.content

    @staticmethod
    def test_overview_doc_none_when_overview_missing() -> None:
        assert RAGImporter._create_overview_doc(_make_film(overview=None), 1, {}) is None
        assert RAGImporter._create_overview_doc(_make_film(overview="   "), 1, {}) is None

    @staticmethod
    def test_overview_doc_without_tagline() -> None:
        doc = RAGImporter._create_overview_doc(_make_film(tagline=None), 1, {})
        assert doc is not None
        assert "Tagline:" not in doc.content


class TestCreateConsensusDoc:
    """RAGImporter._create_consensus_doc — critics consensus embedding."""

    @staticmethod
    def test_consensus_doc_includes_header_and_critique() -> None:
        film = _make_film()
        doc = RAGImporter._create_consensus_doc(film, tmdb_id=948, metadata={})
        assert doc is not None
        assert doc.source_type == "critics_consensus"
        assert doc.source_id == 948
        assert "Director: John Carpenter" in doc.content
        assert "Critique: Scary, suspenseful, and stylish." in doc.content

    @staticmethod
    def test_consensus_doc_none_when_consensus_missing() -> None:
        assert RAGImporter._create_consensus_doc(_make_film(critics_consensus=None), 1, {}) is None
        assert RAGImporter._create_consensus_doc(_make_film(critics_consensus=""), 1, {}) is None


class TestBuildMetadata:
    """RAGImporter._build_metadata — JSONB payload for filtering/display."""

    @staticmethod
    def test_metadata_exposes_all_enriched_fields() -> None:
        meta = RAGImporter._build_metadata(_make_film())
        assert meta["title"] == "Halloween"
        assert meta["year"] == "1978"
        assert meta["genres"] == ["Horror", "Thriller"]
        assert meta["keywords"] == ["slasher", "masked killer", "babysitter"]
        assert meta["cast"] == ["Jamie Lee Curtis", "Donald Pleasence", "P. J. Soles"]
        assert meta["director"] == "John Carpenter"
        assert meta["writers"] == ["John Carpenter", "Debra Hill"]
        assert meta["runtime"] == 91
        assert meta["vote_average"] == 7.7
        assert meta["tomatometer"] == 96
        assert meta["tomatometer_state"] == "certified_fresh"
        assert meta["imdb_rating"] == 7.7
        assert meta["aggregated_score"] == 8.4

    @staticmethod
    def test_metadata_truncates_cast_to_metadata_limit() -> None:
        film = _make_film(cast=[f"Actor{i}" for i in range(METADATA_CAST_LIMIT + 5)])
        meta = RAGImporter._build_metadata(film)
        assert len(meta["cast"]) == METADATA_CAST_LIMIT
        assert meta["cast"][-1] == f"Actor{METADATA_CAST_LIMIT - 1}"

    @staticmethod
    def test_metadata_cast_limit_greater_than_content_limit() -> None:
        """Frontend gets richer cast than the embedding content."""
        assert METADATA_CAST_LIMIT > CONTENT_CAST_LIMIT

    @staticmethod
    def test_metadata_year_none_when_release_date_missing() -> None:
        meta = RAGImporter._build_metadata(_make_film(release_date=None))
        assert meta["year"] is None

    @staticmethod
    def test_metadata_handles_missing_optional_fields() -> None:
        sparse: dict[str, Any] = {"tmdb_id": 1, "title": "X"}
        meta = RAGImporter._build_metadata(sparse)
        assert meta["genres"] == []
        assert meta["keywords"] == []
        assert meta["cast"] == []
        assert meta["director"] is None
        assert meta["runtime"] is None
        assert meta["tomatometer_state"] is None
        assert meta["aggregated_score"] is None
