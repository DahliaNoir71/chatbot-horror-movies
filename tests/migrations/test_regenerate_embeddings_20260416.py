"""Unit tests for hash-based incremental embedding regeneration.

Tests the pure planning logic (`_compare_and_plan`, `_rebuild_document`)
directly with synthetic data, plus an end-to-end smoke test of `run()`
with mocked DB engines and embedding service.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from scripts.migrations.regenerate_embeddings_20260416 import (
    DocRow,
    EmbeddingRegenerator,
    RegenStats,
)

from src.database.importer.rag_importer import RAGImporter

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


def _film_dict(**overrides: Any) -> dict[str, Any]:
    """Build a minimal film dict in the shape RAGImporter helpers expect."""
    base: dict[str, Any] = {
        "tmdb_id": 9552,
        "title": "The Exorcist",
        "title_fr": "L'Exorciste",
        "overview": "A girl gets possessed.",
        "overview_fr": "Une jeune fille est possédée.",
        "tagline": "Something beyond comprehension.",
        "release_date": "1973-12-26",
        "alternative_titles": ["L'Exorciste : Version Intégrale"],
        "director": "William Friedkin",
        "cast": ["Ellen Burstyn", "Linda Blair"],
        "keywords": ["possession", "exorcism"],
        "genres": ["Horror"],
        "critics_consensus": "A genuinely frightening classic.",
    }
    base.update(overrides)
    return base


def _doc_row(
    *, source_type: str = "film_overview",
    source_id: int = 9552,
    content_hash: str | None = None,
) -> DocRow:
    return DocRow(
        doc_id=uuid4(),
        source_type=source_type,
        source_id=source_id,
        content_hash=content_hash,
    )


def _make_regenerator() -> EmbeddingRegenerator:
    """Build a regenerator with all dependencies mocked."""
    return EmbeddingRegenerator(
        embedding_service=MagicMock(),
        horrorbot_engine=MagicMock(),
        vectors_engine=MagicMock(),
        batch_size=8,
    )


# -----------------------------------------------------------------------------
# Pure planning logic
# -----------------------------------------------------------------------------


class TestComparePlan:
    """`_compare_and_plan` — needs_regen flag and counters."""

    @staticmethod
    def test_compute_plan_all_null_hashes_marks_all_for_regen() -> None:
        """First-run scenario: every doc has content_hash=None → all regen."""
        rows = [_doc_row(source_id=9552), _doc_row(source_id=948)]
        films = {9552: _film_dict(tmdb_id=9552), 948: _film_dict(tmdb_id=948, title="Halloween")}
        stats = RegenStats()

        plans = EmbeddingRegenerator._compare_and_plan(rows, films, stats)

        assert all(p.needs_regen for p in plans)
        assert stats.docs_to_regenerate == 2
        assert stats.docs_skipped_unchanged == 0

    @staticmethod
    def test_compute_plan_matching_hash_skipped() -> None:
        """Doc with content_hash matching the rebuilt content's hash → skip."""
        film = _film_dict()
        rebuilt = EmbeddingRegenerator._rebuild_document(film, "film_overview")
        assert rebuilt is not None
        matching_hash = RAGImporter._compute_content_hash(rebuilt)

        row = _doc_row(content_hash=matching_hash)
        stats = RegenStats()

        plans = EmbeddingRegenerator._compare_and_plan(
            [row], {row.source_id: film}, stats,
        )

        assert plans[0].needs_regen is False
        assert stats.docs_skipped_unchanged == 1
        assert stats.docs_to_regenerate == 0

    @staticmethod
    def test_compute_plan_mismatching_hash_marked() -> None:
        """Stale content_hash → flagged for regen."""
        row = _doc_row(content_hash="00000000000000000000000000000000")
        stats = RegenStats()

        plans = EmbeddingRegenerator._compare_and_plan(
            [row], {row.source_id: _film_dict()}, stats,
        )

        assert plans[0].needs_regen is True
        assert stats.docs_to_regenerate == 1


# -----------------------------------------------------------------------------
# dry-run + orphan handling
# -----------------------------------------------------------------------------


class TestRunBehavior:
    """`run()` with mocked DB I/O — orchestration semantics."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_embedding_service() -> None:
        """dry_run=True must skip embedding generation entirely."""
        regen = _make_regenerator()
        regen._fetch_all_doc_rows = AsyncMock(  # type: ignore[method-assign]
            return_value=[_doc_row()],
        )
        regen._fetch_films = AsyncMock(  # type: ignore[method-assign]
            return_value={9552: _film_dict()},
        )

        stats = await regen.run(dry_run=True)

        assert stats.docs_to_regenerate == 1
        assert stats.docs_regenerated == 0
        regen._embedding_service.generate_batch.assert_not_called()

    @staticmethod
    @pytest.mark.asyncio
    async def test_missing_film_logs_warning_and_skips() -> None:
        """Doc referencing a tmdb_id absent from films → counted in failed."""
        regen = _make_regenerator()
        regen._fetch_all_doc_rows = AsyncMock(  # type: ignore[method-assign]
            return_value=[_doc_row(source_id=999_999)],
        )
        regen._fetch_films = AsyncMock(  # type: ignore[method-assign]
            return_value={},
        )

        stats = await regen.run(dry_run=True)

        assert stats.docs_failed == 1
        assert any("999999" in e for e in stats.errors)
        assert stats.docs_to_regenerate == 0


# -----------------------------------------------------------------------------
# FR fields surface in rebuilt content
# -----------------------------------------------------------------------------


class TestBilingualRebuild:
    """`_rebuild_document` integrates `_build_header` bilingual changes from 0.A.4."""

    @staticmethod
    def test_rebuild_uses_fr_fields_when_present() -> None:
        """title_fr and overview_fr both surface in the rebuilt content."""
        film = _film_dict()
        content = EmbeddingRegenerator._rebuild_document(film, "film_overview")

        assert content is not None
        assert "The Exorcist / L'Exorciste" in content
        assert "Une jeune fille est possédée." in content
        assert "Alternative titles: L'Exorciste : Version Intégrale" in content
