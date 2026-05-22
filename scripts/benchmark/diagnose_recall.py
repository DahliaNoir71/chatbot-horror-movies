"""Recall diagnostic for Axe-2 benchmark queries.

For each question, locates every `expected_tmdb_id` in three retrieval
lists — the raw vector neighbourhood, the BM25 hits and the fused
(RRF + popularity) pool — and reports its rank in each. Pinpoints whether
a Hit@5 miss is a vector recall failure (expected film absent from every
list), a pool-cut (found by the embedding but past the production
`vector_top_k` / similarity cutoff) or a ranking failure (in the fused
pool but buried below the top-5). No LLM, no reranker.

The vector column is a *wide* diagnostic view (top-50, near-zero
threshold); the fused column reflects the production pool (vector top-20
at threshold 0.3 + BM25 top-20).

Usage:
    uv run --group ml python -m scripts.benchmark.diagnose_recall
    uv run --group ml python -m scripts.benchmark.diagnose_recall --question Q26,Q27
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import TypedDict

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.services.rag.bm25_retriever import BM25MultilingualRetriever, get_bm25_retriever
from src.services.rag.hybrid_retriever import HybridRetriever
from src.services.rag.reranker import RerankerService, get_reranker_service
from src.services.rag.retriever import DocumentRetriever, get_document_retriever
from src.settings import settings

_FIXTURE = Path(__file__).parents[2] / "tests" / "fixtures" / "axis2_benchmark.json"
_VECTOR_DIAG_K = 50
_VECTOR_DIAG_THRESHOLD = 0.01  # near-zero; 0.0 would be falsy and reset to the default
_BM25_K = 20
_FUSED_K = 40
_RERANK_INPUT_K = 5  # the pipeline reranks search()'s final_top_k docs
_TOP_SHOW = 8  # how many vector hits to print verbatim per query

_VERDICT_LABEL = {
    "OK": "OK — film attendu dans le top-5 fusionné",
    "RANKING": "RANKING — dans le pool fusionné mais sous le top-5",
    "POOL_CUT": "POOL — vu par l'embedding/BM25 mais hors pool prod (vector top-20 @ seuil 0.3)",
    "UNREACHABLE": "HORS DE PORTÉE — absent du vectoriel (top-50) et du BM25",
}


class _Query(TypedDict):
    id: str
    query: str
    expected_tmdb_ids: list[int]


class _Ranks(TypedDict):
    """Rank (1-based) of one tmdb_id across the three retrieval lists."""

    tmdb_id: int
    vector: int | None
    vector_sim: float | None
    bm25: int | None
    fused: int | None


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def _load_queries() -> list[_Query]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _filter(queries: list[_Query], ids: list[str]) -> list[_Query]:
    if not ids:
        return queries
    wanted = set(ids)
    return [q for q in queries if q["id"] in wanted]


# ---------------------------------------------------------------------------
# Retrieval + rank computation
# ---------------------------------------------------------------------------


def _rank(tmdb_id: int, ids: list[int]) -> int | None:
    """Return the 1-based position of tmdb_id in ids, or None if absent."""
    for i, tid in enumerate(ids, start=1):
        if tid == tmdb_id:
            return i
    return None


def _compute_ranks(
    expected: list[int],
    vec: list[tuple[int, float]],
    bm25: list[int],
    fused: list[int],
) -> list[_Ranks]:
    """Locate each expected tmdb_id in the three ordered id lists."""
    vec_ids = [tid for tid, _ in vec]
    sims = dict(vec)
    return [
        _Ranks(
            tmdb_id=tid,
            vector=_rank(tid, vec_ids),
            vector_sim=sims.get(tid),
            bm25=_rank(tid, bm25),
            fused=_rank(tid, fused),
        )
        for tid in expected
    ]


async def _diagnose(
    q: _Query,
    vector: DocumentRetriever,
    bm25: BM25MultilingualRetriever,
    hybrid: HybridRetriever,
    reranker: RerankerService,
) -> tuple[list[_Ranks], list[tuple[str, int, float]], list[tuple[float, int, bool]]]:
    """Run retrieval + rerank for a query and locate its expected films.

    Returns:
        The per-expected-id ranks; the top vector hits as
        (title, tmdb_id, similarity); and the reranked fused top-5 as
        (rerank_score, tmdb_id, is_expected) — what the pipeline's
        circuit-breaker actually sees.
    """
    vec_docs = await asyncio.to_thread(
        vector.retrieve, q["query"], _VECTOR_DIAG_K, _VECTOR_DIAG_THRESHOLD
    )
    bm25_hits = await bm25.search(q["query"], _BM25_K)
    fused = await hybrid.search(q["query"], top_k=_FUSED_K)
    rows = _compute_ranks(
        q["expected_tmdb_ids"],
        [(d.source_id, d.similarity) for d in vec_docs],
        [h.tmdb_id for h in bm25_hits],
        [d.source_id for d in fused],
    )
    top = [
        (str(d.metadata.get("title") or f"id={d.source_id}"), d.source_id, d.similarity)
        for d in vec_docs[:_TOP_SHOW]
    ]
    expected = set(q["expected_tmdb_ids"])
    reranked_docs = await asyncio.to_thread(reranker.rerank, q["query"], fused[:_RERANK_INPUT_K])
    reranked = [(d.rerank_score or 0.0, d.source_id, d.source_id in expected) for d in reranked_docs]
    return rows, top, reranked


def _classify(rows: list[_Ranks]) -> str:
    """Classify a query by the best fate of its expected films."""
    fused_ranks = [r["fused"] for r in rows if r["fused"] is not None]
    if any(fr <= 5 for fr in fused_ranks):
        return "OK"
    if fused_ranks:
        return "RANKING"
    seen = any(r["vector"] is not None or r["bm25"] is not None for r in rows)
    return "POOL_CUT" if seen else "UNREACHABLE"


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


def _fmt_cell(rank: int | None, extra: str = "") -> str:
    return "—" if rank is None else f"#{rank}{extra}"


def _print_rerank(reranked: list[tuple[float, int, bool]]) -> None:
    """Print the reranked fused top-5 and flag the circuit-breaker."""
    floor = settings.retrieval.min_rerank_score
    print(f"  rerank du top-5 fusionné (circuit-breaker garde >= {floor}) :")
    if not reranked:
        print("    (vide — reranker a tout filtré sous RERANKER_MIN_SCORE)")
        return
    for score, tid, is_expected in reranked:
        cut = "" if score >= floor else "  [coupé]"
        mark = "  <<< ATTENDU" if is_expected else ""
        print(f"    {score:+.2f}  [{tid}]{cut}{mark}")
    if not any(score >= floor for score, _, _ in reranked):
        print("    >> CIRCUIT BREAKER — 0 source")


def _print_query(
    q: _Query,
    rows: list[_Ranks],
    top: list[tuple[str, int, float]],
    reranked: list[tuple[float, int, bool]],
) -> None:
    print(f"\n{q['id']} | {q['query']}")
    print(f"  {'tmdb_id':<9} {'vector':<16} {'bm25':<7} {'fused':<7}")
    for r in rows:
        sim = f" ({r['vector_sim']:.3f})" if r["vector_sim"] is not None else ""
        print(
            f"  {r['tmdb_id']:<9} "
            f"{_fmt_cell(r['vector'], sim):<16} "
            f"{_fmt_cell(r['bm25']):<7} "
            f"{_fmt_cell(r['fused']):<7}"
        )
    print(f"  >> {_VERDICT_LABEL[_classify(rows)]}")
    print(f"  vecteur top-{_TOP_SHOW} réellement retourné :")
    for title, tid, sim in top:
        print(f"    {sim:.3f}  [{tid}] {title}")
    if not top:
        print("    (vide)")
    _print_rerank(reranked)


def _print_summary(verdicts: list[str]) -> None:
    counts = {key: verdicts.count(key) for key in _VERDICT_LABEL}
    print(f"\n{'=' * 70}")
    print(f"  {len(verdicts)} questions Axe-2")
    for key, label in _VERDICT_LABEL.items():
        print(f"  {counts[key]:>2}  {label}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _run(queries: list[_Query]) -> None:
    """Build retrievers, diagnose every query, dispose the DB engines."""
    engine_h = create_async_engine(settings.database.async_url, pool_pre_ping=True)
    engine_v = create_async_engine(settings.database.vectors_async_url, pool_pre_ping=True)
    hybrid = HybridRetriever(
        vector_retriever=get_document_retriever(),
        bm25_retriever=get_bm25_retriever(),
        horrorbot_session_factory=async_sessionmaker(engine_h, expire_on_commit=False),
        vectors_session_factory=async_sessionmaker(engine_v, expire_on_commit=False),
        settings=settings.retrieval,
    )
    vector = get_document_retriever()
    bm25 = get_bm25_retriever()
    reranker = get_reranker_service()
    verdicts: list[str] = []
    try:
        for q in queries:
            rows, top, reranked = await _diagnose(q, vector, bm25, hybrid, reranker)
            _print_query(q, rows, top, reranked)
            verdicts.append(_classify(rows))
    finally:
        await engine_h.dispose()
        await engine_v.dispose()
    _print_summary(verdicts)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="", metavar="Q26,Q27")
    args = parser.parse_args()

    ids = [q.strip() for q in args.question.split(",") if q.strip()]
    queries = _filter(_load_queries(), ids)
    print(f"Recall diagnostic: {len(queries)} questions (vector=top-50, fused=pool prod)")
    asyncio.run(_run(queries))


if __name__ == "__main__":
    main()
