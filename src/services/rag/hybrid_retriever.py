"""Hybrid retriever fusing vector similarity, multilingual BM25 and popularity.

Two parallel retrievals (vector + BM25) are merged via Reciprocal Rank
Fusion on `tmdb_id` (the shared logical key between
`rag_documents.source_id` and `films.tmdb_id`). A popularity boost
derived from TMDB's `vote_count` and `popularity` lifts genre classics
above obscure homonymous films at equivalent semantic similarity.

For BM25-only candidates that the vector store missed entirely, one
`rag_document` per film is fetched in bulk so the LLM still gets text
to ground its answer on.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.services.rag.bm25_retriever import BM25MultilingualRetriever, BM25Result
from src.services.rag.retriever import DocumentRetriever, RetrievedDocument, get_document_retriever
from src.settings import settings
from src.settings.retrieval import RetrievalSettings

# Popularity normalization constants (chosen so a typical "very popular"
# horror film hits ~1.0 after log1p):
#   vote_count ≈ 22 000 → log1p / 10 ≈ 1.0
#   popularity ≈ 400    → log1p / 6  ≈ 1.0
_VOTE_COUNT_DIVISOR = 10.0
_POPULARITY_DIVISOR = 6.0
_VOTE_WEIGHT = 0.7
_POP_WEIGHT = 0.3


@dataclass
class FusedCandidate:
    """One film surviving the RRF fusion step (per-tmdb_id)."""

    tmdb_id: int
    rrf_score: float
    base_doc: RetrievedDocument | None
    bm25_hit: BM25Result | None


_SELECT_POPULARITY_SQL = text("""
    SELECT tmdb_id, vote_count, popularity
    FROM films
    WHERE tmdb_id = ANY(:ids)
""")

# DISTINCT ON picks one rag_document per tmdb_id, preferring overview
# (richest text), then critics_consensus, then metadata-only.
_SELECT_DOCS_SQL = text("""
    SELECT DISTINCT ON (source_id)
        id, content, source_type, source_id, metadata
    FROM rag_documents
    WHERE source_id = ANY(:ids)
    ORDER BY source_id,
        CASE source_type
            WHEN 'film_overview' THEN 1
            WHEN 'critics_consensus' THEN 2
            WHEN 'film_metadata' THEN 3
            ELSE 9
        END
""")


class HybridRetriever:
    """Fuse vector similarity and multilingual BM25 via RRF, with popularity boost.

    Attributes:
        _vector: Synchronous vector retriever (called via to_thread).
        _bm25: Async multilingual BM25 retriever.
        _horrorbot_session_factory: Async session for `horrorbot` (popularity).
        _vectors_session_factory: Async session for `horrorbot_vectors`
            (supplementary docs for BM25-only hits).
        _settings: Tunable retrieval weights and top-K caps.
    """

    def __init__(
        self,
        vector_retriever: DocumentRetriever,
        bm25_retriever: BM25MultilingualRetriever,
        horrorbot_session_factory: async_sessionmaker[AsyncSession],
        vectors_session_factory: async_sessionmaker[AsyncSession],
        settings: RetrievalSettings | None = None,
    ) -> None:
        self._vector = vector_retriever
        self._bm25 = bm25_retriever
        self._horrorbot_session_factory = horrorbot_session_factory
        self._vectors_session_factory = vectors_session_factory
        self._settings = settings or RetrievalSettings()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[RetrievedDocument]:
        """Run hybrid retrieval and return the top-K boosted documents.

        Args:
            query: User query.
            top_k: Maximum results; defaults to `settings.final_top_k`.

        Returns:
            Documents ordered by `final_score` descending (length ≤ top_k).
        """
        top_k = top_k or self._settings.final_top_k
        vector_results, bm25_results = await self._fetch_parallel(query)
        fused = self._rrf_fuse(vector_results, bm25_results, self._settings)
        if not fused:
            return []
        final = await self._apply_popularity_boost(fused)
        return sorted(final, key=lambda d: d.final_score or 0.0, reverse=True)[:top_k]

    # -------------------------------------------------------------------------
    # Parallel retrieval
    # -------------------------------------------------------------------------

    async def _fetch_parallel(
        self,
        query: str,
    ) -> tuple[list[RetrievedDocument], list[BM25Result]]:
        """Run vector and BM25 retrieval concurrently."""
        vec_task = asyncio.to_thread(
            self._vector.retrieve,
            query,
            self._settings.vector_top_k,
        )
        bm25_task = self._bm25.search(query, self._settings.bm25_top_k)
        return await asyncio.gather(vec_task, bm25_task)

    # -------------------------------------------------------------------------
    # RRF fusion
    # -------------------------------------------------------------------------

    @staticmethod
    def _rrf_fuse(
        vec: list[RetrievedDocument],
        bm25: list[BM25Result],
        settings: RetrievalSettings,
    ) -> list[FusedCandidate]:
        """Merge per-list ranks into a single RRF score keyed on tmdb_id.

        The vector list may contain multiple docs for the same film
        (overview + consensus); only the best-ranked is kept and used as
        the `base_doc` for the candidate.

        Args:
            vec: Ordered vector retrieval results.
            bm25: Ordered BM25 retrieval results.
            settings: Provides RRF k and per-list weights.

        Returns:
            List of `FusedCandidate`, unsorted.
        """
        vec_doc_by_tmdb: dict[int, RetrievedDocument] = {}
        vec_rank: dict[int, int] = {}
        for rank, doc in enumerate(vec, start=1):
            if doc.source_id not in vec_doc_by_tmdb:
                vec_doc_by_tmdb[doc.source_id] = doc
                vec_rank[doc.source_id] = rank

        bm25_rank = {hit.tmdb_id: rank for rank, hit in enumerate(bm25, start=1)}
        bm25_hits = {hit.tmdb_id: hit for hit in bm25}

        all_ids = set(vec_rank) | set(bm25_rank)
        return [
            FusedCandidate(
                tmdb_id=tid,
                rrf_score=_rrf_score(
                    vec_rank.get(tid),
                    bm25_rank.get(tid),
                    settings,
                ),
                base_doc=vec_doc_by_tmdb.get(tid),
                bm25_hit=bm25_hits.get(tid),
            )
            for tid in all_ids
        ]

    # -------------------------------------------------------------------------
    # Popularity boost
    # -------------------------------------------------------------------------

    async def _apply_popularity_boost(
        self,
        fused: list[FusedCandidate],
    ) -> list[RetrievedDocument]:
        """Attach `final_score` to each candidate, fetching missing docs.

        Two bulk queries are issued in parallel: popularity metrics from
        `horrorbot.films` and supplementary `rag_documents` for the
        BM25-only candidates that lack a `base_doc`.

        Args:
            fused: Output of `_rrf_fuse`.

        Returns:
            List of `RetrievedDocument` with `final_score` populated.
        """
        tmdb_ids = [c.tmdb_id for c in fused]
        missing_ids = [c.tmdb_id for c in fused if c.base_doc is None]
        metrics, extra_docs = await asyncio.gather(
            self._fetch_popularity_metrics(tmdb_ids),
            self._fetch_supplementary_docs(missing_ids),
        )
        return self._build_results(fused, metrics, extra_docs)

    def _build_results(
        self,
        fused: list[FusedCandidate],
        metrics: dict[int, tuple[int, float]],
        extra_docs: dict[int, RetrievedDocument],
    ) -> list[RetrievedDocument]:
        """Stitch RRF scores + popularity boost into RetrievedDocuments."""
        results: list[RetrievedDocument] = []
        for c in fused:
            doc = c.base_doc or extra_docs.get(c.tmdb_id)
            if doc is None:
                continue  # film has no rag_document — drop silently
            vote_count, popularity = metrics.get(c.tmdb_id, (0, 0.0))
            pop_score = self._compute_popularity_score(vote_count, popularity)
            doc.final_score = c.rrf_score + self._settings.popularity_weight * pop_score
            results.append(doc)
        return results

    async def _fetch_popularity_metrics(
        self,
        tmdb_ids: list[int],
    ) -> dict[int, tuple[int, float]]:
        """Bulk-fetch (vote_count, popularity) per tmdb_id from horrorbot.films."""
        if not tmdb_ids:
            return {}
        async with self._horrorbot_session_factory() as session:
            rows = await session.execute(_SELECT_POPULARITY_SQL, {"ids": tmdb_ids})
            return {
                row.tmdb_id: (int(row.vote_count or 0), float(row.popularity or 0.0))
                for row in rows
            }

    async def _fetch_supplementary_docs(
        self,
        tmdb_ids: list[int],
    ) -> dict[int, RetrievedDocument]:
        """Fetch one rag_document per tmdb_id (preferring film_overview)."""
        if not tmdb_ids:
            return {}
        async with self._vectors_session_factory() as session:
            rows = await session.execute(_SELECT_DOCS_SQL, {"ids": tmdb_ids})
            return {row.source_id: _row_to_retrieved_doc(row) for row in rows}

    @staticmethod
    def _compute_popularity_score(vote_count: int, popularity: float) -> float:
        """Combine log-normalized vote_count and popularity into one score.

        `vote_count` carries 0.7 weight (signal of audience reach) and
        `popularity` 0.3 (TMDB's recency-biased trend metric). Both go
        through `log1p` to compress long-tail outliers.

        Args:
            vote_count: TMDB vote_count.
            popularity: TMDB popularity score.

        Returns:
            Normalized popularity score in roughly [0, 1.5].
        """
        vote_norm = math.log1p(vote_count) / _VOTE_COUNT_DIVISOR
        pop_norm = math.log1p(popularity) / _POPULARITY_DIVISOR
        return _VOTE_WEIGHT * vote_norm + _POP_WEIGHT * pop_norm

    # -------------------------------------------------------------------------
    # Sync adapter — preserves the DocumentRetriever interface used by
    # RAGPipeline so the swap is transparent to existing sync callers.
    # -------------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        match_count: int | None = None,
        **_ignored: Any,
    ) -> list[RetrievedDocument]:
        """Sync wrapper around `search()` for compatibility with `RAGPipeline`.

        Must NOT be invoked from inside a running event loop — use the
        async `search()` method directly in async contexts.

        Args:
            query: User query.
            match_count: Optional override for `final_top_k`.
            **_ignored: Swallows extra DocumentRetriever-style kwargs
                (`similarity_threshold`, `source_type`) that don't apply here.

        Returns:
            Retrieved documents ordered by `final_score` desc.

        Raises:
            RuntimeError: When called from within a running event loop.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.search(query, top_k=match_count))
        msg = (
            "HybridRetriever.retrieve() called from a running event loop. "
            "Use `await retriever.search(query, top_k=...)` instead."
        )
        raise RuntimeError(msg)


# -----------------------------------------------------------------------------
# Pure helpers
# -----------------------------------------------------------------------------


def _rrf_score(
    vec_rank: int | None,
    bm25_rank: int | None,
    settings: RetrievalSettings,
) -> float:
    """Compute weighted RRF over the two rank lists.

    Films absent from a list contribute nothing — the formula handles
    `None` by skipping the term entirely.

    Args:
        vec_rank: 1-based rank in the vector list, or None.
        bm25_rank: 1-based rank in the BM25 list, or None.
        settings: RRF k + per-list weights.

    Returns:
        Combined RRF score (higher is better).
    """
    score = 0.0
    if vec_rank is not None:
        score += settings.vector_weight / (settings.rrf_k + vec_rank)
    if bm25_rank is not None:
        score += settings.bm25_weight / (settings.rrf_k + bm25_rank)
    return score


def _row_to_retrieved_doc(row: Any) -> RetrievedDocument:
    """Map a `_SELECT_DOCS_SQL` row to a `RetrievedDocument`."""
    return RetrievedDocument(
        id=row.id,
        content=row.content,
        source_type=row.source_type,
        source_id=row.source_id,
        metadata=row.metadata if isinstance(row.metadata, dict) else {},
        similarity=0.0,  # BM25-only doc — no cosine similarity available
    )


# -----------------------------------------------------------------------------
# DI factories (singletons via lru_cache)
# -----------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _horrorbot_session_factory() -> async_sessionmaker[AsyncSession]:
    """Singleton async session factory for the `horrorbot` database."""
    engine = create_async_engine(settings.database.async_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


@lru_cache(maxsize=1)
def _vectors_session_factory() -> async_sessionmaker[AsyncSession]:
    """Singleton async session factory for the `horrorbot_vectors` database."""
    engine = create_async_engine(
        settings.database.vectors_async_url,
        pool_pre_ping=True,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@lru_cache(maxsize=1)
def get_hybrid_retriever() -> HybridRetriever:
    """Get singleton HybridRetriever wired to all dependencies.

    Reuses the singleton language detector, BM25 retriever and vector
    retriever from their respective modules. Connection pools and
    lingua's compiled language profiles are not re-created per request.
    """
    # Local imports avoid a circular import: bm25_retriever's factory
    # itself imports `_horrorbot_session_factory` from this module.
    from src.services.rag.bm25_retriever import get_bm25_retriever

    return HybridRetriever(
        vector_retriever=get_document_retriever(),
        bm25_retriever=get_bm25_retriever(),
        horrorbot_session_factory=_horrorbot_session_factory(),
        vectors_session_factory=_vectors_session_factory(),
        settings=settings.retrieval,
    )
