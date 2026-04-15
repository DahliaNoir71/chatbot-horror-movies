"""A/B comparison: baseline vs candidate embedding model on FR queries.

Compares the current production embedder (baseline) against a multilingual
candidate by re-embedding a corpus sample and running each FR query through
both. Produces a markdown report with per-query top-K results, similarity
distributions, and encoding latency.

Usage::

    uv run --group ml python scripts/ab_embedding_models.py \\
        --queries tests/data/ab_queries_fr.jsonl \\
        --sample-size 5000

The candidate model loads its own copy of a corpus subset in memory — no
writes to pgvector. Safe to re-run.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sqlalchemy import create_engine, text

from src.settings import settings

BASELINE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CANDIDATE_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 5


def load_queries(path: Path) -> list[str]:
    queries: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            queries.append(obj["query_text"])
    return queries


def fetch_corpus_sample(sample_size: int) -> list[dict]:
    """Pull a random sample of rag_documents (content + source metadata)."""
    engine = create_engine(settings.database.vectors_sync_url)
    sql = text(
        """
        SELECT id::text AS id, content, source_type, source_id, metadata
        FROM rag_documents
        ORDER BY random()
        LIMIT :n
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"n": sample_size}).mappings().all()
    return [dict(r) for r in rows]


def encode_corpus(model, texts: list[str], batch_size: int = 64) -> np.ndarray:
    return model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )


def encode_query(model, query: str) -> tuple[np.ndarray, float]:
    t0 = time.perf_counter()
    vec = model.encode(query, convert_to_numpy=True, normalize_embeddings=True)
    return vec, time.perf_counter() - t0


def top_k(query_vec: np.ndarray, corpus_matrix: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    sims = corpus_matrix @ query_vec
    idx = np.argpartition(-sims, range(min(k, len(sims))))[:k]
    idx = idx[np.argsort(-sims[idx])]
    return idx, sims[idx]


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(values, p))


def render_report(
    queries: list[str],
    baseline_results: list[dict],
    candidate_results: list[dict],
    sample_size: int,
) -> str:
    baseline_lat = [r["latency_ms"] for r in baseline_results]
    candidate_lat = [r["latency_ms"] for r in candidate_results]
    baseline_top1 = [r["top_sims"][0] for r in baseline_results if r["top_sims"]]
    candidate_top1 = [r["top_sims"][0] for r in candidate_results if r["top_sims"]]
    overlaps = [
        jaccard(b["top_ids"], c["top_ids"])
        for b, c in zip(baseline_results, candidate_results)
    ]

    lines = [
        f"# A/B Embedding Models — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"- **Baseline**: `{BASELINE_MODEL}`",
        f"- **Candidate**: `{CANDIDATE_MODEL}`",
        f"- **Queries**: {len(queries)} (FR)",
        f"- **Corpus sample**: {sample_size} documents (random subset of rag_documents)",
        f"- **Top-K**: {TOP_K}",
        "",
        "## Aggregate metrics",
        "",
        "| Metric | Baseline | Candidate |",
        "|---|---|---|",
        f"| Top-1 similarity (mean) | {np.mean(baseline_top1):.4f} | {np.mean(candidate_top1):.4f} |",
        f"| Top-1 similarity (median) | {np.median(baseline_top1):.4f} | {np.median(candidate_top1):.4f} |",
        f"| Encode latency p50 (ms) | {_percentile(baseline_lat, 50):.1f} | {_percentile(candidate_lat, 50):.1f} |",
        f"| Encode latency p95 (ms) | {_percentile(baseline_lat, 95):.1f} | {_percentile(candidate_lat, 95):.1f} |",
        f"| Top-{TOP_K} Jaccard overlap (mean) | — | {np.mean(overlaps):.3f} |",
        "",
        "Note: top-1 similarity values are not directly comparable across models",
        "(different distributions). Inspect per-query results below for relevance.",
        "",
        "## Per-query top-K (manual inspection)",
        "",
    ]

    for i, (q, b, c) in enumerate(zip(queries, baseline_results, candidate_results), 1):
        lines.append(f"### Q{i}. `{q}`")
        lines.append(f"- Top-{TOP_K} Jaccard overlap: **{jaccard(b['top_ids'], c['top_ids']):.2f}**")
        lines.append("")
        lines.append("**Baseline top-K:**")
        for sim, snippet in zip(b["top_sims"], b["top_snippets"]):
            lines.append(f"- `{sim:.3f}` — {snippet}")
        lines.append("")
        lines.append("**Candidate top-K:**")
        for sim, snippet in zip(c["top_sims"], c["top_snippets"]):
            lines.append(f"- `{sim:.3f}` — {snippet}")
        lines.append("")

    return "\n".join(lines)


def _snippet(doc: dict, max_len: int = 140) -> str:
    meta = doc.get("metadata") or {}
    title = meta.get("title") or meta.get("name") or doc.get("source_type", "?")
    year = meta.get("year") or meta.get("release_year") or ""
    content = (doc.get("content") or "").replace("\n", " ").strip()
    if len(content) > max_len:
        content = content[: max_len - 1] + "…"
    head = f"**{title}**" + (f" ({year})" if year else "")
    return f"{head} — {content}"


def run_one_model(model_name: str, queries: list[str], corpus: list[dict]) -> list[dict]:
    from sentence_transformers import SentenceTransformer

    print(f"\n[{model_name}] loading model...")
    model = SentenceTransformer(model_name, device="cpu")

    print(f"[{model_name}] encoding {len(corpus)} corpus docs...")
    matrix = encode_corpus(model, [d["content"] for d in corpus])

    print(f"[{model_name}] running {len(queries)} queries...")
    results: list[dict] = []
    for q in queries:
        vec, latency = encode_query(model, q)
        idx, sims = top_k(vec, matrix, TOP_K)
        results.append(
            {
                "latency_ms": latency * 1000,
                "top_ids": [corpus[i]["id"] for i in idx],
                "top_sims": [float(s) for s in sims],
                "top_snippets": [_snippet(corpus[i]) for i in idx],
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path,
                        default=Path("tests/data/ab_queries_fr.jsonl"))
    parser.add_argument("--sample-size", type=int, default=5000,
                        help="Random corpus sample size to re-embed (default: 5000).")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("docs/mlops-reports"))
    args = parser.parse_args()

    if not args.queries.exists():
        print(f"ERROR: queries file not found: {args.queries}")
        print("Run: uv run python scripts/extract_fr_queries.py first.")
        return 1

    queries = load_queries(args.queries)
    if not queries:
        print(f"ERROR: no queries in {args.queries}")
        return 1
    print(f"Loaded {len(queries)} FR queries from {args.queries}")

    print(f"Sampling {args.sample_size} docs from rag_documents...")
    corpus = fetch_corpus_sample(args.sample_size)
    print(f"  Got {len(corpus)} docs.")
    if not corpus:
        print("ERROR: rag_documents is empty. Run the RAG importer first.")
        return 1

    baseline = run_one_model(BASELINE_MODEL, queries, corpus)
    candidate = run_one_model(CANDIDATE_MODEL, queries, corpus)

    report = render_report(queries, baseline, candidate, len(corpus))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"ab-embedding-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    out.write_text(report, encoding="utf-8")
    print(f"\nReport written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
