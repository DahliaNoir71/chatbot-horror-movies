"""Bilingual BM25 retriever over `films.search_vector_{fr,en}`.

Uses PostgreSQL's weighted tsvector columns (maintained by the trigger
in `05_search_vectors.sql` / `07_title_fr_fallback.sql`) to run
full-text search with BM25-style ranking via `ts_rank_cd`.

The query is matched against both the FR and EN tsvector columns in a
single pass, and is expanded into an *OR* of its lexemes so that:

* conversational filler ("parle-moi du film ...") no longer forces an
  AND match the target film cannot satisfy — `plainto_tsquery` required
  every token, including words absent from any film's tsvector;
* an English title typed inside a French sentence still reaches the
  `english`-stemmed `search_vector_en`;
* proper nouns (director / cast / keywords, indexed with the `simple`
  dictionary) match without being mangled by language stemming.

The lexemes are produced in the `french`, `english` and `simple`
configurations and unioned, so each can find its matching column.
`ts_rank_cd` honors the per-column weights (A = titles + director,
B = cast, C = overview + keywords), so a title hit dominates an
incidental overview hit.

Returns `tmdb_id` (not `films.id`) as the logical key so results join
directly with `rag_documents.source_id` for hybrid retrieval.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.monitoring.metrics import RAG_BM25_DURATION, RAG_BM25_RESULTS_COUNT, RAG_QUERY_LANGUAGE
from src.services.rag.language_detector import LanguageDetector


@dataclass(frozen=True)
class BM25Result:
    """One BM25 hit — carries `tmdb_id` for joining with `rag_documents`.

    Attributes:
        tmdb_id: TMDB identifier (logical key shared with rag_documents.source_id).
        title: Canonical EN title.
        title_fr: French title if present.
        bm25_score: Combined `ts_rank_cd` score across both tsvector columns.
        source: `"fr"` when the FR column carried the stronger match, `"en"` otherwise.
    """

    tmdb_id: int
    title: str
    title_fr: str | None
    bm25_score: float
    source: Literal["fr", "en"]


# In this all-horror corpus many films are literally titled "... Film",
# "Horror ...", etc. Left in the query, the domain words "film" / "horreur"
# match those titles at weight A and bury the real entity, so they are
# stripped before the tsquery is built. Grammatical stopwords are left to
# the `french` / `english` text-search configs.
_NOISE_WORDS: frozenset[str] = frozenset(
    {
        "film",
        "films",
        "movie",
        "movies",
        "cinema",
        "cinéma",
        "horreur",
        "horror",
        "épouvante",
        "epouvante",
    }
)
_TOKEN_RE = re.compile(r"\w+")


def _strip_noise(query: str) -> str:
    """Drop domain noise words and apostrophe artifacts from a raw query.

    Args:
        query: Raw user query.

    Returns:
        The query reduced to its content tokens, or the original query
        when stripping would leave nothing to search on.
    """
    kept = [
        tok for tok in _TOKEN_RE.findall(query.lower()) if len(tok) > 1 and tok not in _NOISE_WORDS
    ]
    return " ".join(kept) if kept else query


# Minimum TMDB vote_count for a film to be retrievable. The corpus holds
# ~63k films but roughly 87% are obscure zero-vote shorts; every benchmarked
# film clears 200 votes, so 100 is a safe floor that strips the noise.
_MIN_VOTE_COUNT = 100


# The query is turned into an OR of its lexemes by rewriting the `&`
# operators that `websearch_to_tsquery` emits into `|`. The same text is
# lexed in three configurations and unioned, so French-stemmed,
# English-stemmed and raw (`simple`) lexemes can each find their column.
# `websearch_to_tsquery` parses arbitrary user input without ever raising.
#
# Two corpus-noise guards: only films with `vote_count >= :min_votes` enter
# the candidate set, and ranking uses `ts_filter(..., '{a,b}')` so only
# title / director / cast lexemes score — overview text (weight C) is full
# of conversational verbs ("raconte", ...) that would bury the real entity.
_SEARCH_SQL = text("""
    WITH tsq AS (
        SELECT (
            replace(websearch_to_tsquery('french',  :q)::text, '&', '|')::tsquery ||
            replace(websearch_to_tsquery('english', :q)::text, '&', '|')::tsquery ||
            replace(websearch_to_tsquery('simple',  :q)::text, '&', '|')::tsquery
        ) AS q
    ),
    ranked AS (
        SELECT
            f.tmdb_id,
            f.title,
            f.title_fr,
            ts_rank_cd(ts_filter(f.search_vector_fr, '{a,b}'), tsq.q) AS rank_fr,
            ts_rank_cd(ts_filter(f.search_vector_en, '{a,b}'), tsq.q) AS rank_en
        FROM films f, tsq
        WHERE (f.search_vector_fr @@ tsq.q OR f.search_vector_en @@ tsq.q)
          AND f.vote_count >= :min_votes
    )
    SELECT tmdb_id, title, title_fr, rank_fr, rank_en
    FROM ranked
    ORDER BY rank_fr + rank_en DESC
    LIMIT :lim
""")


class BM25MultilingualRetriever:
    """Full-text search over `films.search_vector_{fr,en}`.

    Attributes:
        _session_factory: Async session factory bound to the horrorbot DB.
        _language_detector: Injected detector — used only to label the
            `RAG_QUERY_LANGUAGE` metric; retrieval itself queries both
            columns and is language-agnostic.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        language_detector: LanguageDetector,
    ) -> None:
        self._session_factory = session_factory
        self._language_detector = language_detector

    async def search(self, query: str, top_k: int = 20) -> list[BM25Result]:
        """Search both tsvector columns and return the top-K BM25 hits.

        Empty queries return `[]` without hitting the DB.

        Args:
            query: Raw user query.
            top_k: Maximum number of results to return.

        Returns:
            List of `BM25Result` ordered by best match first (length ≤ top_k).
        """
        if not query or not query.strip():
            return []
        RAG_QUERY_LANGUAGE.labels(self._language_detector.detect(query)).inc()
        t0 = time.perf_counter()
        results = await self._run_search(query, top_k)
        RAG_BM25_DURATION.observe(time.perf_counter() - t0)
        RAG_BM25_RESULTS_COUNT.observe(len(results))
        return results

    async def _run_search(self, query: str, top_k: int) -> list[BM25Result]:
        """Execute the OR-expanded full-text query and map rows to results."""
        async with self._session_factory() as session:
            rows = await session.execute(
                _SEARCH_SQL,
                {"q": _strip_noise(query), "lim": top_k, "min_votes": _MIN_VOTE_COUNT},
            )
            return [_row_to_result(row) for row in rows]


def _row_to_result(row: Any) -> BM25Result:
    """Map a `_SEARCH_SQL` row to a `BM25Result`."""
    rank_fr = float(row.rank_fr or 0.0)
    rank_en = float(row.rank_en or 0.0)
    return BM25Result(
        tmdb_id=row.tmdb_id,
        title=row.title,
        title_fr=row.title_fr,
        bm25_score=rank_fr + rank_en,
        source="fr" if rank_fr >= rank_en else "en",
    )


# -----------------------------------------------------------------------------
# DI factory
# -----------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_bm25_retriever() -> BM25MultilingualRetriever:
    """Get the singleton BM25 retriever wired to horrorbot + language detector."""
    # Local import avoids a circular import: the session factory lives in
    # hybrid_retriever, whose own factory imports this module.
    from src.services.rag.hybrid_retriever import _horrorbot_session_factory
    from src.services.rag.language_detector import get_language_detector

    return BM25MultilingualRetriever(
        session_factory=_horrorbot_session_factory(),
        language_detector=get_language_detector(),
    )
