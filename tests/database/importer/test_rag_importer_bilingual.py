"""Unit tests for RAGImporter bilingual FR/EN content generation."""

from __future__ import annotations

import hashlib
from typing import Any

from src.database.importer.rag_importer import RAGImporter


def _make_film(**overrides: Any) -> dict[str, Any]:
    """Build a minimal film with FR enrichment."""
    base: dict[str, Any] = {
        "tmdb_id": 9552,
        "title": "The Exorcist",
        "title_fr": "L'Exorciste",
        "release_date": "1973-12-26",
        "overview": "A mother seeks help for her possessed daughter.",
        "overview_fr": "Une mère cherche de l'aide pour sa fille possédée.",
        "alternative_titles": ["L'Exorciste : Version Intégrale"],
        "tagline": "Something almost beyond comprehension.",
        "genres": ["Horror"],
        "keywords": ["possession", "exorcism"],
        "cast": ["Ellen Burstyn", "Linda Blair"],
        "director": "William Friedkin",
        "critics_consensus": "A genuinely frightening classic.",
    }
    base.update(overrides)
    return base


class TestBuildHeaderBilingual:
    """_build_header includes FR title and alternative titles when present."""

    @staticmethod
    def test_header_with_fr_title() -> None:
        header = RAGImporter._build_header(_make_film())
        assert "The Exorcist / L'Exorciste (1973)" in header
        assert "Alternative titles: L'Exorciste : Version Intégrale" in header

    @staticmethod
    def test_header_without_fr_title() -> None:
        header = RAGImporter._build_header(
            _make_film(title_fr=None, alternative_titles=[]),
        )
        assert "The Exorcist (1973)" in header
        assert " / " not in header
        assert "Alternative titles:" not in header

    @staticmethod
    def test_header_fr_title_equal_to_title_is_not_duplicated() -> None:
        """A film with identical title_fr and title must not render '... / ...'."""
        header = RAGImporter._build_header(
            _make_film(title="Saw", title_fr="Saw", alternative_titles=[]),
        )
        assert "Saw / Saw" not in header
        assert header.startswith("Saw (")


class TestCreateOverviewDocBilingual:
    """_create_overview_doc contains EN + FR overviews when both present."""

    @staticmethod
    def test_overview_doc_bilingual() -> None:
        doc = RAGImporter._create_overview_doc(_make_film(), tmdb_id=9552, metadata={})
        assert doc is not None
        assert "A mother seeks help for her possessed daughter." in doc.content
        assert "Une mère cherche de l'aide pour sa fille possédée." in doc.content

    @staticmethod
    def test_overview_doc_en_only() -> None:
        doc = RAGImporter._create_overview_doc(
            _make_film(overview_fr=None), tmdb_id=9552, metadata={},
        )
        assert doc is not None
        assert "A mother seeks help" in doc.content
        assert "Une mère" not in doc.content

    @staticmethod
    def test_overview_doc_skips_duplicate_fr() -> None:
        """When overview_fr equals overview, no duplication in content."""
        duplicated = "Same text in both."
        doc = RAGImporter._create_overview_doc(
            _make_film(overview=duplicated, overview_fr=duplicated),
            tmdb_id=9552,
            metadata={},
        )
        assert doc is not None
        assert doc.content.count(duplicated) == 1


class TestMetadataFrFields:
    """_build_metadata exposes title_fr, overview_fr, alternative_titles."""

    @staticmethod
    def test_metadata_includes_fr_fields() -> None:
        meta = RAGImporter._build_metadata(_make_film())
        assert meta["title_fr"] == "L'Exorciste"
        assert meta["overview_fr"] == "Une mère cherche de l'aide pour sa fille possédée."
        assert meta["alternative_titles"] == ["L'Exorciste : Version Intégrale"]

    @staticmethod
    def test_metadata_fr_fields_default_when_missing() -> None:
        meta = RAGImporter._build_metadata({"tmdb_id": 1, "title": "X"})
        assert meta["title_fr"] is None
        assert meta["overview_fr"] is None
        assert meta["alternative_titles"] == []


class TestContentHash:
    """_compute_content_hash: MD5 of UTF-8 content."""

    @staticmethod
    def test_content_hash_computed() -> None:
        content = "hello world"
        expected = hashlib.md5(
            content.encode("utf-8"), usedforsecurity=False,
        ).hexdigest()
        assert RAGImporter._compute_content_hash(content) == expected

    @staticmethod
    def test_content_hash_stable_across_calls() -> None:
        h1 = RAGImporter._compute_content_hash("payload")
        h2 = RAGImporter._compute_content_hash("payload")
        assert h1 == h2
        assert len(h1) == 32

    @staticmethod
    def test_content_hash_differs_for_different_content() -> None:
        assert (
            RAGImporter._compute_content_hash("a")
            != RAGImporter._compute_content_hash("b")
        )
