"""Sweep popularity_weight and measure Hit@5 on Axe-2 benchmark queries.

Instantiates a HybridRetriever for each candidate weight, runs all 15
Axe-2 questions against the live database, and prints an ASCII table of
Hit@5 results. No LLM is invoked -- pure retrieval benchmark.

Usage:
    uv run --group ml python -m scripts.benchmark.sweep_popularity_weight
    uv run --group ml python -m scripts.benchmark.sweep_popularity_weight --weights 0.0 0.003 0.01 0.05
    uv run --group ml python -m scripts.benchmark.sweep_popularity_weight --debug
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import TypedDict

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.services.rag.bm25_retriever import get_bm25_retriever
from src.services.rag.hybrid_retriever import HybridRetriever
from src.services.rag.retriever import get_document_retriever
from src.settings import settings
from src.settings.retrieval import RetrievalSettings

_FIXTURE = Path(__file__).parents[2] / "tests" / "fixtures" / "axis2_benchmark.json"
# RRF scores span ~0.006-0.016; a popularity term above that magnitude
# overrides semantic rank entirely. The calibrated range is 0.001-0.01
# (see RetrievalSettings.popularity_weight) — the sweep must stay there.
_DEFAULT_WEIGHTS: list[float] = [0.0, 0.003, 0.005, 0.01, 0.02, 0.05]
_TOP_K = 5


class _Query(TypedDict):
    id: str
    query: str
    expected_tmdb_ids: list[int]


def _load_queries() -> list[_Query]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _build_retriever(
    weight: float,
    factory_h: async_sessionmaker,
    factory_v: async_sessionmaker,
) -> HybridRetriever:
    """Construct a HybridRetriever with a specific popularity_weight."""
    return HybridRetriever(
        vector_retriever=get_document_retriever(),
        bm25_retriever=get_bm25_retriever(),
        horrorbot_session_factory=factory_h,
        vectors_session_factory=factory_v,
        settings=RetrievalSettings(popularity_weight=weight),
    )


async def _evaluate(
    retriever: HybridRetriever,
    queries: list[_Query],
    debug: bool = False,
) -> list[bool]:
    """Return one bool per query: True if any expected tmdb_id appears in top-K."""
    hits: list[bool] = []
    for q in queries:
        docs = await retriever.search(q["query"], top_k=_TOP_K)
        found = {doc.source_id for doc in docs}
        hit = bool(found & set(q["expected_tmdb_ids"]))
        hits.append(hit)
        if debug:
            status = "HIT " if hit else "MISS"
            titles = [d.metadata.get("title", f"id={d.source_id}") for d in docs]
            print(
                f"  [{status}] {q['id']} | found={sorted(found)} "
                f"| expected={q['expected_tmdb_ids']} | top5={titles}"
            )
    return hits


async def _run_sweep(
    queries: list[_Query],
    weights: list[float],
    debug: bool = False,
) -> list[tuple[float, list[bool]]]:
    """Run the full sweep across all weights, sharing DB connections."""
    engine_h = create_async_engine(settings.database.async_url, pool_pre_ping=True)
    engine_v = create_async_engine(
        settings.database.vectors_async_url, pool_pre_ping=True
    )
    factory_h: async_sessionmaker = async_sessionmaker(
        engine_h, expire_on_commit=False
    )
    factory_v: async_sessionmaker = async_sessionmaker(
        engine_v, expire_on_commit=False
    )

    results: list[tuple[float, list[bool]]] = []
    try:
        for weight in weights:
            retriever = _build_retriever(weight, factory_h, factory_v)
            print(f"  weight={weight:.3f} ...", end="\n" if debug else " ", flush=True)
            hits = await _evaluate(retriever, queries, debug=debug)
            score = sum(hits)
            if not debug:
                print(f"{score}/{len(hits)}")
            else:
                print(f"  -> {score}/{len(hits)}\n")
            results.append((weight, hits))
    finally:
        await engine_h.dispose()
        await engine_v.dispose()

    return results


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

_W0, _W1, _W2 = 8, 7, 7  # fixed column widths: weight | hit@5 | pct


def _print_table(
    queries: list[_Query],
    results: list[tuple[float, list[bool]]],
) -> None:
    q_ids = [q["id"] for q in queries]
    col_w = [max(len(qid), 3) for qid in q_ids]

    def _sep() -> str:
        parts = ["-" * (_W0 + 2), "-" * (_W1 + 2), "-" * (_W2 + 2)]
        parts += ["-" * (cw + 2) for cw in col_w]
        return "+" + "+".join(parts) + "+"

    def _row(cells: list[str]) -> str:
        parts = [
            cells[0].ljust(_W0),
            cells[1].rjust(_W1),
            cells[2].rjust(_W2),
        ]
        parts += [cells[3 + i].center(col_w[i]) for i in range(len(q_ids))]
        return "| " + " | ".join(parts) + " |"

    sep = _sep()
    print(sep)
    print(_row(["weight", "hit@5", "score"] + q_ids))
    print(sep)
    for weight, hits in results:
        score = sum(hits)
        cells = [
            f"{weight:.3f}",
            f"{score}/{len(hits)}",
            f"{score / len(hits):.0%}",
        ] + ["Y" if h else "." for h in hits]
        print(_row(cells))
    print(sep)


def _recommend(results: list[tuple[float, list[bool]]]) -> float:
    """Return optimal weight (argmax Hit@5, tie-break = smallest weight)."""
    best_weight, best_hits = max(results, key=lambda r: (sum(r[1]), -r[0]))
    best_score = sum(best_hits)
    n = len(best_hits)
    print(f"\nOptimal: popularity_weight={best_weight:.3f}  =>  {best_score}/{n} Hit@5")
    return best_weight


def _propose_env(weight: float) -> None:
    print(
        f"\nTo apply, add/update in .env:\n"
        f"  RETRIEVAL_POPULARITY_WEIGHT={weight}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--weights",
        nargs="+",
        type=float,
        default=_DEFAULT_WEIGHTS,
        metavar="W",
        help="popularity_weight values to test (default: %(default)s)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print found tmdb_ids and top-5 titles for each query (first weight only)",
    )
    args = parser.parse_args()

    queries = _load_queries()
    weights = args.weights[:1] if args.debug else args.weights
    print(f"Axe-2 sweep: {len(weights)} weights x {len(queries)} queries\n")

    results = asyncio.run(_run_sweep(queries, weights, debug=args.debug))

    print()
    _print_table(queries, results)
    best = _recommend(results)
    _propose_env(best)


if __name__ == "__main__":
    main()
