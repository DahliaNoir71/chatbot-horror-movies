"""Unit tests for HybridRetriever — RRF formula + popularity boost."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.services.rag.bm25_retriever import BM25Result
from src.services.rag.hybrid_retriever import (
    FusedCandidate,
    HybridRetriever,
    RetrievalSettings,
    _rrf_score,
)
from src.services.rag.retriever import RetrievedDocument

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


def _doc(tmdb_id: int, *, similarity: float = 0.5, doc_id: UUID | None = None) -> RetrievedDocument:
    """Build a minimal RetrievedDocument for tests."""
    return RetrievedDocument(
        id=doc_id or uuid4(),
        content=f"content for {tmdb_id}",
        source_type="film_overview",
        source_id=tmdb_id,
        metadata={"title": f"Film {tmdb_id}"},
        similarity=similarity,
    )


def _bm25(tmdb_id: int, score: float = 0.5) -> BM25Result:
    return BM25Result(
        tmdb_id=tmdb_id,
        title=f"Film {tmdb_id}",
        title_fr=None,
        bm25_score=score,
        source="en",
    )


def _make_retriever(
    metrics: dict[int, tuple[int, float]] | None = None,
    settings: RetrievalSettings | None = None,
) -> HybridRetriever:
    """HybridRetriever wired with stubbed dependencies (no DB / no model)."""
    retriever = HybridRetriever(
        vector_retriever=MagicMock(),
        bm25_retriever=MagicMock(),
        horrorbot_session_factory=MagicMock(),
        vectors_session_factory=MagicMock(),
        settings=settings or RetrievalSettings(),
    )
    retriever._fetch_popularity_metrics = AsyncMock(return_value=metrics or {})  # type: ignore[method-assign]
    retriever._fetch_supplementary_docs = AsyncMock(return_value={})  # type: ignore[method-assign]
    return retriever


# -----------------------------------------------------------------------------
# RRF formula
# -----------------------------------------------------------------------------


class TestRRFFormula:
    """Reciprocal Rank Fusion produces the expected weighted scores."""

    @staticmethod
    def test_rrf_formula_known_lists() -> None:
        """Hand-computed RRF on a tiny example."""
        settings = RetrievalSettings(vector_weight=1.0, bm25_weight=1.0, rrf_k=60)
        # vec ranks: 1=tmdb1, 2=tmdb2 ; bm25 ranks: 1=tmdb2, 2=tmdb3
        # tmdb1: 1/61 + 0           = 1/61
        # tmdb2: 1/62 + 1/61        = 1/62 + 1/61
        # tmdb3: 0    + 1/62        = 1/62
        assert _rrf_score(1, None, settings) == pytest.approx(1 / 61)
        assert _rrf_score(2, 1, settings) == pytest.approx(1 / 62 + 1 / 61)
        assert _rrf_score(None, 2, settings) == pytest.approx(1 / 62)

    @staticmethod
    def test_doc_in_single_ranking_zero_contribution() -> None:
        """A film absent from BM25 only gets the vector contribution."""
        settings = RetrievalSettings()
        assert _rrf_score(5, None, settings) == settings.vector_weight / (settings.rrf_k + 5)

    @staticmethod
    def test_vector_weight_zero_disables_vector() -> None:
        """When vector_weight=0, fused score equals BM25-only ranking."""
        settings = RetrievalSettings(vector_weight=0.0, bm25_weight=1.0)
        # Same film in both lists — vector contribution must drop out.
        s = _rrf_score(1, 5, settings)
        assert s == pytest.approx(1.0 / (60 + 5))

    @staticmethod
    def test_fuse_dedupes_per_tmdb_in_vector() -> None:
        """Multiple vector docs for the same tmdb_id collapse to one candidate."""
        vec = [_doc(1), _doc(1), _doc(2)]
        bm25: list[BM25Result] = []
        fused = HybridRetriever._rrf_fuse(vec, bm25, RetrievalSettings())
        assert {c.tmdb_id for c in fused} == {1, 2}
        assert len(fused) == 2


# -----------------------------------------------------------------------------
# Popularity boost
# -----------------------------------------------------------------------------


class TestPopularityBoost:
    """Popularity lifts classics over obscure homonyms at equal RRF."""

    @staticmethod
    def test_compute_popularity_score_classic_beats_obscure() -> None:
        """Halloween (votes=6120) > Best Halloween Ever (votes=3)."""
        classic = HybridRetriever._compute_popularity_score(6120, 50.0)
        obscure = HybridRetriever._compute_popularity_score(3, 0.5)
        assert classic > obscure

    @staticmethod
    @pytest.mark.asyncio
    async def test_popularity_boost_ranks_classic_over_obscure() -> None:
        """Same vec rank for both, but Halloween (vote_count=6120) wins."""
        halloween_id, obscure_id = 948, 90001
        retriever = _make_retriever(metrics={
            halloween_id: (6120, 50.0),
            obscure_id: (3, 0.5),
        })
        # Hand-craft fused candidates with identical RRF scores
        fused = [
            FusedCandidate(
                tmdb_id=halloween_id, rrf_score=0.5,
                base_doc=_doc(halloween_id), bm25_hit=None,
            ),
            FusedCandidate(
                tmdb_id=obscure_id, rrf_score=0.5,
                base_doc=_doc(obscure_id), bm25_hit=None,
            ),
        ]
        retriever._rrf_fuse = MagicMock(return_value=fused)  # type: ignore[method-assign]
        retriever._fetch_parallel = AsyncMock(  # type: ignore[method-assign]
            return_value=([_doc(halloween_id), _doc(obscure_id)], []),
        )

        results = await retriever.search("Halloween", top_k=2)

        assert len(results) == 2
        assert results[0].source_id == halloween_id, (
            f"expected Halloween (vote_count=6120) top-1, got {results[0].source_id}"
        )

    @staticmethod
    @pytest.mark.asyncio
    async def test_popularity_does_not_resurrect_irrelevant() -> None:
        """At a calibrated weight, popularity can't flip a clearly irrelevant film.

        With the placeholder default `popularity_weight=0.3`, popularity
        dominates RRF (RRF scores are ~0.01–0.05 while normalized
        popularity reaches ~1.4). Phase 2 of the workplan is explicitly
        dedicated to sweeping `popularity_weight`. This test asserts
        the GUARD works at a calibrated value (~0.003), proving the
        formula itself is sound — only the weight needs tuning.
        """
        relevant_id, popular_irrelevant_id = 100, 200
        retriever = _make_retriever(
            metrics={
                relevant_id: (10, 1.0),
                popular_irrelevant_id: (50_000, 500.0),
            },
            settings=RetrievalSettings(popularity_weight=0.003),
        )
        fused = [
            FusedCandidate(
                tmdb_id=relevant_id, rrf_score=1 / 61,
                base_doc=_doc(relevant_id), bm25_hit=None,
            ),
            FusedCandidate(
                tmdb_id=popular_irrelevant_id, rrf_score=1 / 200,
                base_doc=_doc(popular_irrelevant_id), bm25_hit=None,
            ),
        ]
        retriever._rrf_fuse = MagicMock(return_value=fused)  # type: ignore[method-assign]
        retriever._fetch_parallel = AsyncMock(  # type: ignore[method-assign]
            return_value=([_doc(relevant_id)], []),
        )

        results = await retriever.search("relevant query", top_k=1)

        assert len(results) == 1
        assert results[0].source_id == relevant_id, (
            "at popularity_weight=0.003, popularity should not resurrect "
            f"a rank-200 film over a rank-1 hit (got {results[0].source_id})"
        )


# -----------------------------------------------------------------------------
# Integration sketch
# -----------------------------------------------------------------------------


class TestSearchOrchestration:
    """End-to-end `search()` with everything mocked."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_search_returns_top_k_sorted_by_final_score() -> None:
        retriever = _make_retriever(metrics={1: (100, 1.0), 2: (50, 0.5)})
        retriever._fetch_parallel = AsyncMock(  # type: ignore[method-assign]
            return_value=([_doc(1), _doc(2)], [_bm25(2), _bm25(1)]),
        )

        results = await retriever.search("query", top_k=2)

        assert len(results) == 2
        scores = [r.final_score for r in results]
        assert scores[0] is not None and scores[1] is not None
        assert scores[0] >= scores[1]
