"""Bilingual BM25 retriever over `films.search_vector_{fr,en}`.

Uses PostgreSQL's weighted tsvector columns (maintained by the trigger
in `05_search_vectors.sql`) to run full-text search with BM25-style
ranking via `ts_rank_cd`. Queries are routed to the appropriate column
based on language detection; ambiguous or code-switching queries hit
both columns and the results are fused via Reciprocal Rank Fusion.

Returns `tmdb_id` (not `films.id`) as the logical key so results join
directly with `rag_documents.source_id` for hybrid retrieval.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.services.rag.language_detector import LanguageDetector

# Reciprocal Rank Fusion constant (Cormack et al. 2009). k=60 is the
# widely cited default that dampens the top-rank dominance without
# flattening the distribution.
_RRF_K = 60


@dataclass(frozen=True)
class BM25Result:
    """One BM25 hit — carries `tmdb_id` for joining with `rag_documents`.

    Attributes:
        tmdb_id: TMDB identifier (logical key shared with rag_documents.source_id).
        title: Canonical EN title.
        title_fr: French title if present.
        bm25_score: Raw `ts_rank_cd` score (higher is better).
        source: `"fr"` when matched via `search_vector_fr`, `"en"` otherwise.
    """

    tmdb_id: int
    title: str
    title_fr: str | None
    bm25_score: float
    source: Literal["fr", "en"]


_SEARCH_FR_SQL = text("""
    SELECT
        f.tmdb_id,
        f.title,
        f.title_fr,
        ts_rank_cd(f.search_vector_fr, plainto_tsquery('french', :q)) AS score
    FROM films f
    WHERE f.search_vector_fr @@ plainto_tsquery('french', :q)
    ORDER BY score DESC
    LIMIT :lim
""")

_SEARCH_EN_SQL = text("""
    SELECT
        f.tmdb_id,
        f.title,
        f.title_fr,
        ts_rank_cd(f.search_vector_en, plainto_tsquery('english', :q)) AS score
    FROM films f
    WHERE f.search_vector_en @@ plainto_tsquery('english', :q)
    ORDER BY score DESC
    LIMIT :lim
""")


class BM25MultilingualRetriever:
    """Full-text search over `films.search_vector_{fr,en}` with RRF fusion.

    Attributes:
        _session_factory: Async session factory bound to the horrorbot DB.
        _language_detector: Injected detector used to route queries.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        language_detector: LanguageDetector,
    ) -> None:
        self._session_factory = session_factory
        self._language_detector = language_detector

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def search(self, query: str, top_k: int = 20) -> list[BM25Result]:
        """Search and return the top-K BM25 hits across routed columns.

        Empty queries return `[]` without hitting the DB.

        Args:
            query: Raw user query.
            top_k: Maximum number of results to return.

        Returns:
            List of `BM25Result` ordered by best match first (length ≤ top_k).
        """
        if not query or not query.strip():
            return []
        lang = self._language_detector.detect(query)
        if lang == "fr":
            return await self._search_fr(query, top_k)
        if lang == "en":
            return await self._search_en(query, top_k)
        return await self._search_mixed(query, top_k)

    # -------------------------------------------------------------------------
    # Per-language search
    # -------------------------------------------------------------------------

    async def _search_fr(self, query: str, top_k: int) -> list[BM25Result]:
        return await self._run_query(_SEARCH_FR_SQL, query, top_k, source="fr")

    async def _search_en(self, query: str, top_k: int) -> list[BM25Result]:
        return await self._run_query(_SEARCH_EN_SQL, query, top_k, source="en")

    async def _search_mixed(self, query: str, top_k: int) -> list[BM25Result]:
        """Fetch FR and EN lists in parallel and fuse them via RRF."""
        fr_task = self._search_fr(query, top_k)
        en_task = self._search_en(query, top_k)
        fr_results, en_results = await asyncio.gather(fr_task, en_task)
        return self._rrf_merge(fr_results, en_results, top_k)

    async def _run_query(
        self,
        stmt: text,
        query: str,
        top_k: int,
        source: Literal["fr", "en"],
    ) -> list[BM25Result]:
        """Execute one parametrized tsvector query and map rows to results."""
        async with self._session_factory() as session:
            rows = await session.execute(stmt, {"q": query, "lim": top_k})
            return [
                BM25Result(
                    tmdb_id=row.tmdb_id,
                    title=row.title,
                    title_fr=row.title_fr,
                    bm25_score=float(row.score),
                    source=source,
                )
                for row in rows
            ]

    # -------------------------------------------------------------------------
    # RRF fusion
    # -------------------------------------------------------------------------

    @staticmethod
    def _rrf_merge(
        fr: list[BM25Result],
        en: list[BM25Result],
        top_k: int,
        k: int = _RRF_K,
    ) -> list[BM25Result]:
        """Reciprocal Rank Fusion on two BM25 result lists.

        Each document's fused score is the sum of `1 / (k + rank)` across
        the lists in which it appears. When a film has matches in both
        columns, the better-ranked source is retained in the merged hit.

        Args:
            fr: Results from `search_vector_fr`.
            en: Results from `search_vector_en`.
            top_k: Cap on merged output length.
            k: RRF dampening constant (default 60, Cormack et al. 2009).

        Returns:
            Deduplicated merged list (length ≤ top_k), ordered by fused score.
        """
        scores: dict[int, float] = {}
        chosen: dict[int, BM25Result] = {}
        for results in (fr, en):
            for rank, hit in enumerate(results, start=1):
                scores[hit.tmdb_id] = scores.get(hit.tmdb_id, 0.0) + 1.0 / (k + rank)
                current = chosen.get(hit.tmdb_id)
                if current is None or rank < _rank_of(current, results):
                    chosen[hit.tmdb_id] = hit

        merged = sorted(chosen.values(), key=lambda r: scores[r.tmdb_id], reverse=True)
        return merged[:top_k]


def _rank_of(hit: BM25Result, results: list[BM25Result]) -> int:
    """Return 1-based rank of `hit` inside `results`, or a large sentinel."""
    for idx, other in enumerate(results, start=1):
        if other.tmdb_id == hit.tmdb_id:
            return idx
    return 10**9


# -----------------------------------------------------------------------------
# DI factory
# -----------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_bm25_retriever() -> BM25MultilingualRetriever:
    """Get the singleton BM25 retriever wired to horrorbot + language detector."""
    from src.services.rag.hybrid_retriever import _horrorbot_session_factory
    from src.services.rag.language_detector import get_language_detector

    return BM25MultilingualRetriever(
        session_factory=_horrorbot_session_factory(),
        language_detector=get_language_detector(),
    )
