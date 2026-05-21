"""Sweep retrieval hyperparameters and measure Hit@5 on the Axe-2 benchmark.

Probes the 15 Axe-2 questions once against the live database + reranker
(vector retrieval, BM25, popularity, cross-encoder scores are all cached),
then sweeps every combination of:

  * RETRIEVAL_VECTOR_WEIGHT   in {0.3, 0.4, 0.5, 0.6, 0.7}  (bm25 = 1 - vector)
  * RETRIEVAL_RRF_K           in {30, 60, 100}
  * RETRIEVAL_MIN_RERANK_SCORE in {-3.0, -2.0, -1.5, -1.0}

purely in memory. Prints a per-question failure diagnosis (Retrieval vs
Fusion vs Rerank), an ASCII Hit@5 heatmap, and the optimal config. No LLM
is invoked — this is a retrieval-only benchmark.

Usage:
    uv run --group ml python -m scripts.benchmark.sweep_hyperparams
    uv run --group ml python -m scripts.benchmark.sweep_hyperparams --debug
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.services.rag.bm25_retriever import BM25MultilingualRetriever, get_bm25_retriever
from src.services.rag.reranker import RerankerService
from src.services.rag.retriever import DocumentRetriever, RetrievedDocument, get_document_retriever
from src.settings import settings

_FIXTURE = Path(__file__).parents[2] / "tests" / "fixtures" / "axis2_benchmark.json"

# Sweep grid.
_VECTOR_WEIGHTS: tuple[float, ...] = (0.3, 0.4, 0.5, 0.6, 0.7)
_RRF_KS: tuple[int, ...] = (30, 60, 100)
_MIN_RERANKS: tuple[float, ...] = (-3.0, -2.0, -1.5, -1.0)

# Effective production defaults — used as the diagnosis baseline.
_BASELINE: tuple[float, int, float] = (0.5, 60, -2.0)

# Popularity normalization — mirrors HybridRetriever._compute_popularity_score.
_VOTE_DIVISOR, _POP_DIVISOR = 10.0, 6.0
_VOTE_WEIGHT, _POP_WEIGHT = 0.7, 0.3

_STAGES: tuple[str, ...] = ("RETRIEVAL", "FUSION", "RERANK", "HIT")
_SHADES = " .:+#"  # Hit@5 density ramp, low -> high.

# Mirrors hybrid_retriever._SELECT_POPULARITY_SQL / _SELECT_DOCS_SQL. Duplicated
# (not imported) to keep this one-shot benchmark decoupled from service internals.
_POP_SQL = text("SELECT tmdb_id, vote_count, popularity FROM films WHERE tmdb_id = ANY(:ids)")
_DOCS_SQL = text("""
    SELECT DISTINCT ON (source_id) id, content, source_type, source_id, metadata
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


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class _Query(TypedDict):
    id: str
    query: str
    expected_tmdb_ids: list[int]


@dataclass
class _Ctx:
    """Live retrieval dependencies shared across the probe phase."""

    vector: DocumentRetriever
    bm25: BM25MultilingualRetriever
    reranker: RerankerService
    pop_factory: async_sessionmaker[AsyncSession]
    doc_factory: async_sessionmaker[AsyncSession]


@dataclass
class _Probe:
    """Cached, hyperparameter-independent retrieval state for one question.

    Attributes:
        qid: Question id (e.g. "Q23").
        expected: Expected tmdb_ids — a question hits if any appears in top-5.
        vec_rank: tmdb_id -> 1-based rank in the vector top-20 (best doc).
        bm25_rank: tmdb_id -> 1-based rank in the BM25 top-20.
        pop_score: tmdb_id -> normalized popularity score.
        rerank_score: tmdb_id -> cross-encoder score of its chosen document.
        has_doc: tmdb_ids that have a usable rag_document (eligible as source).
    """

    qid: str
    expected: set[int]
    vec_rank: dict[int, int]
    bm25_rank: dict[int, int]
    pop_score: dict[int, float]
    rerank_score: dict[int, float]
    has_doc: set[int]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _load_queries() -> list[_Query]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _pop_score(vote_count: int, popularity: float) -> float:
    """Log-normalized popularity — mirrors HybridRetriever._compute_popularity_score."""
    vote_norm = math.log1p(vote_count) / _VOTE_DIVISOR
    pop_norm = math.log1p(popularity) / _POP_DIVISOR
    return _VOTE_WEIGHT * vote_norm + _POP_WEIGHT * pop_norm


def _rrf(vec_rank: int | None, bm25_rank: int | None, vw: float, k: int) -> float:
    """Weighted RRF score — mirrors hybrid_retriever._rrf_score (bm25_weight = 1 - vw)."""
    score = 0.0
    if vec_rank is not None:
        score += vw / (k + vec_rank)
    if bm25_rank is not None:
        score += (1.0 - vw) / (k + bm25_rank)
    return score


def _rank_vec(
    vec: list[RetrievedDocument],
) -> tuple[dict[int, int], dict[int, RetrievedDocument]]:
    """Dedup the vector list to one (rank, doc) per tmdb_id, keeping best rank."""
    ranks: dict[int, int] = {}
    docs: dict[int, RetrievedDocument] = {}
    for rank, doc in enumerate(vec, start=1):
        if doc.source_id not in docs:
            docs[doc.source_id] = doc
            ranks[doc.source_id] = rank
    return ranks, docs


def _rerank_scores(
    reranker: RerankerService,
    query: str,
    docs: list[RetrievedDocument],
) -> dict[int, float]:
    """Score every candidate doc once; the reranker is built unfiltered."""
    if not docs:
        return {}
    reranked = reranker.rerank(query, docs)
    return {d.source_id: float(d.rerank_score) for d in reranked if d.rerank_score is not None}


# ---------------------------------------------------------------------------
# Probe phase (live DB + models)
# ---------------------------------------------------------------------------


async def _fetch_pop(
    factory: async_sessionmaker[AsyncSession],
    ids: list[int],
) -> dict[int, float]:
    """Bulk-fetch normalized popularity per tmdb_id from horrorbot.films."""
    if not ids:
        return {}
    async with factory() as session:
        rows = await session.execute(_POP_SQL, {"ids": ids})
        return {
            row.tmdb_id: _pop_score(int(row.vote_count or 0), float(row.popularity or 0.0))
            for row in rows
        }


async def _fetch_docs(
    factory: async_sessionmaker[AsyncSession],
    ids: list[int],
) -> dict[int, RetrievedDocument]:
    """Fetch one rag_document per tmdb_id for BM25-only candidates."""
    if not ids:
        return {}
    async with factory() as session:
        rows = await session.execute(_DOCS_SQL, {"ids": ids})
        return {
            row.source_id: RetrievedDocument(
                id=row.id,
                content=row.content,
                source_type=row.source_type,
                source_id=row.source_id,
                metadata=row.metadata if isinstance(row.metadata, dict) else {},
                similarity=0.0,
            )
            for row in rows
        }


async def _probe_one(q: _Query, ctx: _Ctx) -> _Probe:
    """Run retrieval + rerank once for a question, caching all swept-independent state."""
    query = q["query"]
    vec = await asyncio.to_thread(ctx.vector.retrieve, query, settings.retrieval.vector_top_k)
    bm25_hits = await ctx.bm25.search(query, settings.retrieval.bm25_top_k)
    vec_rank, vec_docs = _rank_vec(vec)
    bm25_rank = {hit.tmdb_id: rank for rank, hit in enumerate(bm25_hits, start=1)}
    all_ids = set(vec_rank) | set(bm25_rank)

    extra = await _fetch_docs(ctx.doc_factory, [i for i in all_ids if i not in vec_docs])
    chosen: dict[int, RetrievedDocument] = {**vec_docs, **extra}
    pop = await _fetch_pop(ctx.pop_factory, list(all_ids))
    rerank = await asyncio.to_thread(_rerank_scores, ctx.reranker, query, list(chosen.values()))

    return _Probe(
        qid=q["id"],
        expected=set(q["expected_tmdb_ids"]),
        vec_rank=vec_rank,
        bm25_rank=bm25_rank,
        pop_score=pop,
        rerank_score=rerank,
        has_doc=set(chosen),
    )


async def _probe_all(queries: list[_Query]) -> list[_Probe]:
    """Probe every question, sharing one connection pool per database."""
    engine_h = create_async_engine(settings.database.async_url, pool_pre_ping=True)
    engine_v = create_async_engine(settings.database.vectors_async_url, pool_pre_ping=True)
    ctx = _Ctx(
        vector=get_document_retriever(),
        bm25=get_bm25_retriever(),
        reranker=RerankerService(min_score=-1e9, top_k=10**6),
        pop_factory=async_sessionmaker(engine_h, expire_on_commit=False),
        doc_factory=async_sessionmaker(engine_v, expire_on_commit=False),
    )
    probes: list[_Probe] = []
    try:
        for i, q in enumerate(queries, 1):
            print(f"  [{i:02d}/{len(queries)}] {q['id']} ...", end=" ", flush=True)
            probe = await _probe_one(q, ctx)
            probes.append(probe)
            print(f"{len(probe.has_doc)} candidates")
    finally:
        await engine_h.dispose()
        await engine_v.dispose()
    return probes


# ---------------------------------------------------------------------------
# Sweep phase (pure, in-memory)
# ---------------------------------------------------------------------------


def _final_scores(probe: _Probe, vw: float, k: int) -> dict[int, float]:
    """RRF + popularity score per candidate tmdb_id, for one (vw, k) combo."""
    pop_weight = settings.retrieval.popularity_weight
    scores: dict[int, float] = {}
    for tid in probe.has_doc:
        rrf = _rrf(probe.vec_rank.get(tid), probe.bm25_rank.get(tid), vw, k)
        scores[tid] = rrf + pop_weight * probe.pop_score.get(tid, 0.0)
    return scores


def _top_final(probe: _Probe, vw: float, k: int) -> list[int]:
    """tmdb_ids that survive into the final top-K after RRF + popularity."""
    scores = _final_scores(probe, vw, k)
    ranked = sorted(scores, key=lambda t: scores[t], reverse=True)
    return ranked[: settings.retrieval.final_top_k]


def _surviving(probe: _Probe, vw: float, k: int, min_rerank: float) -> set[int]:
    """Sources returned to the user: final top-K filtered by the rerank floor."""
    floor = max(settings.reranker.min_score, min_rerank)
    return {t for t in _top_final(probe, vw, k) if probe.rerank_score.get(t, -1e9) >= floor}


def _sweep(probes: list[_Probe]) -> dict[tuple[float, int, float], int]:
    """Compute Hit@5 over all questions for every hyperparameter combination."""
    scores: dict[tuple[float, int, float], int] = {}
    for vw in _VECTOR_WEIGHTS:
        for k in _RRF_KS:
            for mr in _MIN_RERANKS:
                scores[(vw, k, mr)] = sum(
                    bool(p.expected & _surviving(p, vw, k, mr)) for p in probes
                )
    return scores


def _recommend(
    scores: dict[tuple[float, int, float], int],
) -> tuple[tuple[float, int, float], int]:
    """Pick the optimal combo: max Hit@5, then strictest rerank, then central vw/k."""

    def key(item: tuple[tuple[float, int, float], int]) -> tuple[int, float, float, float]:
        (vw, k, mr), hits = item
        return (hits, mr, -abs(vw - 0.5), -abs(k - 60))

    best, hits = max(scores.items(), key=key)
    return best, hits


# ---------------------------------------------------------------------------
# Failure diagnosis
# ---------------------------------------------------------------------------


def _stage_for_id(probe: _Probe, tid: int, vw: float, k: int, min_rerank: float) -> str:
    """Pipeline stage an expected film reaches: RETRIEVAL / FUSION / RERANK / HIT."""
    if tid not in probe.has_doc:
        return "RETRIEVAL"  # absent from both top-20 lists, or has no rag_document
    floor = max(settings.reranker.min_score, min_rerank)
    if tid not in _top_final(probe, vw, k):
        stage = "FUSION"
    elif probe.rerank_score.get(tid, -1e9) < floor:
        stage = "RERANK"
    else:
        stage = "HIT"
    return stage


def _classify(probe: _Probe) -> tuple[str, dict[int, str]]:
    """Classify a question under the baseline config; cause = furthest stage reached."""
    vw, k, mr = _BASELINE
    stages = {tid: _stage_for_id(probe, tid, vw, k, mr) for tid in probe.expected}
    cause = max(stages.values(), key=_STAGES.index) if stages else "RETRIEVAL"
    return cause, stages


def _print_trace(probe: _Probe, stages: dict[int, str]) -> None:
    """Print per-expected-id retrieval ranks and rerank score (debug mode)."""
    for tid, stage in sorted(stages.items()):
        vr = probe.vec_rank.get(tid)
        br = probe.bm25_rank.get(tid)
        rr = probe.rerank_score.get(tid)
        rr_txt = f"{rr:.2f}" if rr is not None else "n/a"
        print(
            f"        tmdb={tid:<8} vec_rank={vr!s:<5} bm25_rank={br!s:<5} "
            f"rerank={rr_txt:<7} -> {stage}"
        )


def _print_diagnosis(probes: list[_Probe], debug: bool) -> None:
    """Print the per-question failure diagnosis under the baseline config."""
    vw, k, mr = _BASELINE
    print(f"\n=== Failure diagnosis (baseline vw={vw}, k={k}, min_rerank={mr}) ===")
    print(f"  {'Q#':<5}{'expected tmdb_ids':<26}{'retrieved':<11}{'cause'}")
    counts: dict[str, int] = dict.fromkeys(_STAGES, 0)
    for probe in probes:
        cause, stages = _classify(probe)
        counts[cause] += 1
        retrieved = sum(1 for t in probe.expected if t in probe.vec_rank or t in probe.bm25_rank)
        exp = ", ".join(str(t) for t in sorted(probe.expected))
        print(f"  {probe.qid:<5}{exp:<26}{retrieved}/{len(probe.expected):<9}{cause}")
        if debug:
            _print_trace(probe, stages)
    summary = "  ".join(f"{s}={counts[s]}" for s in _STAGES)
    print(f"\n  Summary: {summary}")
    print("  RETRIEVAL failures need index/query work (out of this sweep's reach);")
    print("  FUSION + RERANK failures are exactly what the sweep below targets.")


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------


def _shade(count: int, total: int) -> str:
    """Map a Hit@5 count to a density character."""
    frac = count / total if total else 0.0
    return _SHADES[min(int(frac * len(_SHADES)), len(_SHADES) - 1)]


def _print_panel(
    scores: dict[tuple[float, int, float], int],
    total: int,
    best: tuple[float, int, float],
    mr: float,
) -> None:
    """Print one vector_weight x rrf_k heatmap panel for a fixed min_rerank."""
    print(f"\n  min_rerank = {mr:>5}")
    print("  vw \\ k    " + "".join(f"k={k:<6}" for k in _RRF_KS))
    for vw in _VECTOR_WEIGHTS:
        cells = []
        for k in _RRF_KS:
            count = scores[(vw, k, mr)]
            mark = "*" if (vw, k, mr) == best else " "
            cells.append(f"{count:>3d}{_shade(count, total)}{mark}  ")
        print(f"  vw={vw:<6} " + "".join(cells))


def _print_heatmap(
    scores: dict[tuple[float, int, float], int],
    total: int,
    best: tuple[float, int, float],
) -> None:
    """Print the full ASCII Hit@5 heatmap (one panel per min_rerank value)."""
    print(f"\n=== Hit@5 heatmap — {total} Axe-2 questions (cell = hits, '*' = optimum) ===")
    for mr in _MIN_RERANKS:
        _print_panel(scores, total, best, mr)
    print(f"\n  density ramp (low -> high): '{_SHADES}'")


def _propose_env(best: tuple[float, int, float], hits: int, total: int) -> None:
    """Print the optimal config and the .env lines that apply it."""
    vw, k, mr = best
    print(
        f"\nOptimal: vector_weight={vw}  rrf_k={k}  min_rerank_score={mr}  =>  {hits}/{total} Hit@5"
    )
    print("\nTo apply, set in .env:")
    print(f"  RETRIEVAL_VECTOR_WEIGHT={vw}")
    print(f"  RETRIEVAL_BM25_WEIGHT={round(1.0 - vw, 2)}")
    print(f"  RETRIEVAL_RRF_K={k}")
    print(f"  RETRIEVAL_MIN_RERANK_SCORE={mr}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print per-expected-id retrieval ranks and rerank scores",
    )
    args = parser.parse_args()

    queries = _load_queries()
    n_combo = len(_VECTOR_WEIGHTS) * len(_RRF_KS) * len(_MIN_RERANKS)
    print(f"Probing {len(queries)} Axe-2 questions against the live DB + reranker ...")
    probes = asyncio.run(_probe_all(queries))

    _print_diagnosis(probes, debug=args.debug)

    print(f"\nSweeping {n_combo} hyperparameter combinations (in-memory) ...")
    scores = _sweep(probes)
    best, hits = _recommend(scores)
    _print_heatmap(scores, len(queries), best)
    _propose_env(best, hits, len(queries))


if __name__ == "__main__":
    main()
