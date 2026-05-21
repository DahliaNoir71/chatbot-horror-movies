"""Full benchmark runner for HorrorBot — 50 questions via POST /api/v1/chat.

Authenticates with JWT, runs all questions, evaluates intent accuracy (Axe 1)
and Hit@5 (Axe 2) automatically, and writes a Markdown report.

Usage:
    uv run python -m scripts.benchmark.run_benchmark
    uv run python -m scripts.benchmark.run_benchmark --limit 5
    uv run python -m scripts.benchmark.run_benchmark --question Q24,Q31,Q37
    uv run python -m scripts.benchmark.run_benchmark --url http://localhost:8000 --user demo --password secret
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TypedDict

import httpx

_FIXTURE = Path(__file__).parents[2] / "tests" / "fixtures" / "benchmark_full.json"
_DEFAULT_URL = "http://localhost:8000"
_DEFAULT_USER = os.environ.get("BENCHMARK_USER", "TheSweak")
_DEFAULT_PASSWORD = os.environ.get("BENCHMARK_PASSWORD", "thx1138")  # nosec B105
_WARMUP_MSG = "Bonjour HorrorBot"
_TIMEOUT = 120.0

_AXE1_IDS = {f"Q{i}" for i in range(1, 21)}
_AXE2_IDS = {f"Q{i}" for i in range(21, 36)}
_NEEDS_DB_IDS = {f"Q{i}" for i in range(1, 11)}
_CONV_IDS = {f"Q{i}" for i in range(11, 16)}
_OFFTOPIC_IDS = {f"Q{i}" for i in range(16, 21)}

# Baseline from manual run 2026-04-15: (hit5, faithfulness)
_BASELINE: dict[str, tuple[int, int]] = {
    "Q3": (0, 1),
    "Q23": (0, 0),
    "Q24": (0, 1),
    "Q31": (0, 1),
    "Q37": (0, 0),
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class BenchmarkQuestion(TypedDict):
    id: str
    axis: int
    question: str
    expected_intent: str
    expected_tmdb_ids: list[int]
    session_group: str | None
    expect_422: bool


class RawResult(TypedDict):
    status_code: int
    intent: str
    confidence: float
    sources: list[dict]
    timings: dict | None
    token_usage: dict
    error: str | None


class BenchmarkResult(TypedDict):
    question: BenchmarkQuestion
    raw: RawResult
    intent_ok: bool | None
    hit5: bool | None
    circuit_breaker: bool  # True if rerank score too low, 0 sources, skips LLM
    faithfulness: str  # always "?" — manual fill post-run


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _load_questions(fixture: Path) -> list[BenchmarkQuestion]:
    return json.loads(fixture.read_text(encoding="utf-8"))


def _filter_questions(
    questions: list[BenchmarkQuestion],
    limit: int | None,
    question_ids: list[str],
) -> list[BenchmarkQuestion]:
    if question_ids:
        ids = set(question_ids)
        questions = [q for q in questions if q["id"] in ids]
    if limit is not None:
        questions = questions[:limit]
    return questions


def _authenticate(base_url: str, username: str, password: str) -> str:
    resp = httpx.post(
        f"{base_url}/api/v1/auth/token",
        json={"username": username, "password": password},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _warmup(base_url: str, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(2):
        with contextlib.suppress(Exception):
            httpx.post(
                f"{base_url}/api/v1/chat",
                json={"message": _WARMUP_MSG},
                headers=headers,
                timeout=_TIMEOUT,
            )


def _env_hash(env_path: Path) -> str:
    if not env_path.exists():
        return "n/a"
    return hashlib.sha1(env_path.read_bytes()).hexdigest()[:8]  # noqa: S324


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------


def _build_payload(question: BenchmarkQuestion, session_map: dict[str, str]) -> dict:
    payload: dict = {"message": question["question"]}
    grp = question["session_group"]
    if grp and grp in session_map:
        payload["session_id"] = session_map[grp]
    return payload


def _post_chat(
    session: httpx.Client,
    base_url: str,
    payload: dict,
    user: str,
    password: str,
    timeout: float,
) -> httpx.Response:
    """POST /api/v1/chat, re-authenticating once if the JWT has expired.

    A full benchmark run (40+ LLM calls) can outlast the token lifetime; a
    401 triggers a fresh login and a single retry so the run completes.

    Args:
        session: HTTP client carrying the bearer token, updated in place
            when a re-authentication happens.
        base_url: API base URL.
        payload: Chat request body.
        user: Benchmark username, for re-authentication.
        password: Benchmark password, for re-authentication.
        timeout: Per-request timeout in seconds.

    Returns:
        The HTTP response — the caller inspects the status code.
    """
    resp = session.post(f"{base_url}/api/v1/chat", json=payload, timeout=timeout)
    if resp.status_code == 401:
        token = _authenticate(base_url, user, password)
        session.headers["Authorization"] = f"Bearer {token}"
        resp = session.post(f"{base_url}/api/v1/chat", json=payload, timeout=timeout)
    return resp


def _send(
    session: httpx.Client,
    base_url: str,
    payload: dict,
    user: str,
    password: str,
) -> tuple[httpx.Response | None, str | None]:
    try:
        resp = _post_chat(session, base_url, payload, user, password, _TIMEOUT)
    except Exception as exc:
        return None, str(exc)
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
    return resp, None


def _call_api(
    session: httpx.Client,
    base_url: str,
    question: BenchmarkQuestion,
    session_map: dict[str, str],
    user: str,
    password: str,
) -> RawResult:
    if question["expect_422"]:
        return _call_expect_422(session, base_url, user, password)

    payload = _build_payload(question, session_map)
    resp, err = _send(session, base_url, payload, user, password)
    if err:
        return _error_result(err)

    body = resp.json()  # type: ignore[union-attr]
    if grp := question["session_group"]:
        session_map[grp] = body["session_id"]
    return RawResult(
        status_code=resp.status_code,  # type: ignore[union-attr]
        intent=body.get("intent", ""),
        confidence=body.get("confidence", 0.0),
        sources=body.get("sources", []),
        timings=body.get("timings"),
        token_usage=body.get("token_usage", {}),
        error=None,
    )


def _call_expect_422(
    session: httpx.Client,
    base_url: str,
    user: str,
    password: str,
) -> RawResult:
    try:
        resp = _post_chat(session, base_url, {"message": ""}, user, password, 10.0)
        code = resp.status_code
    except Exception as exc:
        return _error_result(str(exc))
    return _error_result(None, status_code=code)


def _error_result(msg: str | None, status_code: int = 0) -> RawResult:
    return RawResult(
        status_code=status_code,
        intent="",
        confidence=0.0,
        sources=[],
        timings=None,
        token_usage={},
        error=msg,
    )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _evaluate(question: BenchmarkQuestion, raw: RawResult) -> BenchmarkResult:
    is_breaker = raw["intent"] == "needs_database" and len(raw["sources"]) == 0 and not raw["error"]
    return BenchmarkResult(
        question=question,
        raw=raw,
        intent_ok=_check_intent(question, raw),
        hit5=_check_hit5(question, raw),
        circuit_breaker=is_breaker,
        faithfulness="?",
    )


def _check_intent(question: BenchmarkQuestion, raw: RawResult) -> bool | None:
    if question["expect_422"]:
        return raw["status_code"] == 422
    if raw["error"]:
        return None
    return raw["intent"] == question["expected_intent"]


def _check_hit5(question: BenchmarkQuestion, raw: RawResult) -> bool | None:
    if not question["expected_tmdb_ids"] or raw["error"]:
        return None
    found = {s["tmdb_id"] for s in raw["sources"] if s.get("tmdb_id")}
    return bool(found & set(question["expected_tmdb_ids"]))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _compute_metrics(results: list[BenchmarkResult]) -> dict:
    axe1 = [r for r in results if r["question"]["id"] in _AXE1_IDS]
    axe2 = [r for r in results if r["question"]["id"] in _AXE2_IDS]
    rag = [r for r in results if r["raw"]["timings"] is not None]
    llm_ran = [r for r in rag if not r["circuit_breaker"]]
    totals = [r["raw"]["timings"]["total_ms"] for r in llm_ran]  # type: ignore[index]
    classifs = [r["raw"]["timings"]["classification_ms"] for r in rag]  # type: ignore[index]
    circuit_breaker_count = sum(1 for r in results if r["circuit_breaker"])
    return {
        "intent_ok": sum(1 for r in axe1 if r["intent_ok"] is True),
        "intent_total": len(axe1),
        "hit5_ok": sum(1 for r in axe2 if r["hit5"] is True),
        "hit5_total": len(axe2),
        "circuit_breaker_count": circuit_breaker_count,
        "conf_needs_database": _avg_conf(results, _NEEDS_DB_IDS),
        "conf_conversational": _avg_conf(results, _CONV_IDS),
        "conf_off_topic": _avg_conf(results, _OFFTOPIC_IDS),
        "p50_total_ms": _percentile(totals, 50),
        "p95_total_ms": _percentile(totals, 95),
        "p95_classif_ms": _percentile(classifs, 95),
        "llm_ran_count": len(llm_ran),
    }


def _avg_conf(results: list[BenchmarkResult], ids: set[str]) -> float | None:
    vals = [
        r["raw"]["confidence"]
        for r in results
        if r["question"]["id"] in ids and not r["raw"]["error"]
    ]
    return round(sum(vals) / len(vals), 3) if vals else None


def _percentile(values: list[float], pct: int) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return round(s[min(int(len(s) * pct / 100), len(s) - 1)], 1)


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _ok_cell(val: float | None, threshold: float, lower_is_better: bool = False) -> str:
    if val is None:
        return "—"
    meets = (val < threshold) if lower_is_better else (val >= threshold)
    return "✅" if meets else "❌"


def _render_markdown(results: list[BenchmarkResult], metrics: dict, meta: dict) -> str:
    sections = [
        _render_header(meta),
        _render_grid(results),
        _render_aggregated(metrics),
        _render_diff(results),
    ]
    return "\n\n".join(sections) + "\n"


def _render_header(meta: dict) -> str:
    rows = [
        ("Date", meta["date"]),
        ("Opérateur", meta["operator"]),
        ("Index RAG", "63 656 docs (60 472 `film_overview` + 3 184 `film_metadata`)"),
        ("Sources données", "TMDB uniquement (RT/IMDB désactivés)"),
        ("Embedding", meta.get("embedding", "—")),
        ("Reranker", meta.get("reranker", "—")),
        ("Intent classifier", meta.get("classifier", "—")),
        ("LLM", meta.get("llm", "—")),
        ("Hash `.env` (court)", meta.get("env_hash", "—")),
        ("Warm-up effectué", "oui"),
    ]
    table = "\n".join(f"| {k} | {v} |" for k, v in rows)
    return (
        "# Benchmark HorrorBot — Résultats\n\n"
        "> Voir [benchmark_horrorbot.md](benchmark_horrorbot.md) pour le protocole.\n\n"
        "## Contexte du run\n\n"
        "| Champ | Valeur |\n"
        "|---|---|\n"
        f"{table}"
    )


def _render_grid(results: list[BenchmarkResult]) -> str:
    header = (
        "## Grille de résultats\n\n"
        "Légende : Hit@5 = `1` si ≥1 film attendu présent dans top 5 sources, `0` sinon. "
        "Faithfulness = `?` (jugement manuel post-run).\n\n"
        "| # | Intent retourné | Confidence | Hit@5 | Faithfulness | "
        "Total ms | Classif. ms | Retrieval ms | Rerank ms | LLM ms | "
        "Nb sources | Top similarity | Top rerank | Notes |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    return "\n".join([header] + [_grid_row(r) for r in results])


def _fmt_timings(t: dict | None) -> tuple[str, str, str, str, str]:
    if not t:
        return "—", "—", "n/a", "n/a", "n/a"
    total = f"{t['total_ms']:.0f}" if t.get("total_ms") else "—"
    classif = f"{t['classification_ms']:.0f}" if t.get("classification_ms") else "—"
    retr = f"{t['retrieval_ms']:.0f}" if t.get("retrieval_ms") is not None else "n/a"
    rerank = f"{t['rerank_ms']:.0f}" if t.get("rerank_ms") is not None else "n/a"
    llm = f"{t['generation_ms']:.0f}" if t.get("generation_ms") is not None else "n/a"
    return total, classif, retr, rerank, llm


def _fmt_sources(sources: list[dict]) -> tuple[int, str, str]:
    nb = len(sources)
    if not sources:
        return 0, "—", "—"
    top_sim = f"{sources[0]['similarity_score']:.3f}"
    rr = sources[0].get("rerank_score")
    top_rnk = f"{rr:.2f}" if rr is not None else "—"
    return nb, top_sim, top_rnk


def _grid_row(r: BenchmarkResult) -> str:
    q = r["question"]
    raw = r["raw"]

    if raw["error"] and not q["expect_422"]:
        return f"| {q['id']} | ERROR | — | — | ? | — | — | — | — | — | — | — | — | {raw['error'][:60]} |"

    if q["expect_422"]:
        ok = "✅ 422" if raw["status_code"] == 422 else f"❌ {raw['status_code']}"
        return f"| {q['id']} | {ok} | — | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | HTTP 422 attendu |"

    total, classif, retr, rerank, llm = _fmt_timings(raw["timings"])
    nb, top_sim, top_rnk = _fmt_sources(raw["sources"])
    intent_cell = raw["intent"] + ("" if r["intent_ok"] is not False else " ❌")
    hit5_cell = "n/a" if r["hit5"] is None else ("1" if r["hit5"] else "0")
    note = "(circuit breaker: rerank < -2.0)" if r["circuit_breaker"] else ""
    return (
        f"| {q['id']} | {intent_cell} | {raw['confidence']:.2f} | {hit5_cell} | ? | "
        f"{total} | {classif} | {retr} | {rerank} | {llm} | {nb} | {top_sim} | {top_rnk} | {note} |"
    )


def _aggregated_rows(metrics: dict) -> list[tuple[str, str, str, str, str]]:
    nd = metrics["conf_needs_database"]
    cv = metrics["conf_conversational"]
    ot = metrics["conf_off_topic"]
    p50 = metrics["p50_total_ms"]
    p95 = metrics["p95_total_ms"]
    pc = metrics["p95_classif_ms"]
    breaker = metrics["circuit_breaker_count"]
    llm_ran = metrics["llm_ran_count"]
    return [
        (
            "Intent accuracy (axe 1)",
            f"{metrics['intent_ok']}/{metrics['intent_total']}",
            "19/20",
            "≥ 18/20 (90%)",
            _ok_cell(metrics["intent_ok"], 18),
        ),
        (
            "Confidence `needs_database` (Q1-10)",
            str(nd or "—"),
            "0.993",
            "≥ 0.6",
            _ok_cell(nd, 0.6),
        ),
        (
            "Confidence `conversational` (Q11-15)",
            str(cv or "—"),
            "1.00",
            "≥ 0.5",
            _ok_cell(cv, 0.5),
        ),
        ("Confidence `off_topic` (Q16-20)", str(ot or "—"), "0.755", "≥ 0.5", _ok_cell(ot, 0.5)),
        (
            "Hit@5 (axe 2, 15 questions)",
            f"{metrics['hit5_ok']}/{metrics['hit5_total']}",
            "2/15",
            "≥ 12/15 (80%)",
            _ok_cell(metrics["hit5_ok"], 12),
        ),
        ("Faithfulness (axe 3, 10 questions)", "? (jugement manuel)", "2/10", "≥ 8/10 (80%)", "—"),
        ("Circuit breaker (rerank score < -2.0)", f"{breaker} questions", "n/a", "minimal", "—"),
        (
            f"Latence P50 (LLM-running only, n={llm_ran})",
            f"{p50} ms" if p50 else "—",
            "non capturé",
            "< 15 000 ms",
            _ok_cell(p50, 15000, lower_is_better=True),
        ),
        (
            f"Latence P95 (LLM-running only, n={llm_ran})",
            f"{p95} ms" if p95 else "—",
            "non capturé",
            "< 30 000 ms",
            _ok_cell(p95, 30000, lower_is_better=True),
        ),
        (
            "Latence classification P95 (all)",
            f"{pc} ms" if pc else "—",
            "~1400 ms",
            "< 300 ms",
            _ok_cell(pc, 300, lower_is_better=True),
        ),
    ]


def _render_aggregated(metrics: dict) -> str:
    header = (
        "## Métriques agrégées\n\n"
        "| Métrique | Résultat | Avant (baseline) | Cible | OK ? |\n"
        "|---|---|---|---|---|"
    )
    rows = "\n".join(
        f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |" for r in _aggregated_rows(metrics)
    )
    return f"{header}\n{rows}"


def _render_diff(results: list[BenchmarkResult]) -> str:
    header = (
        "## Diff questions critiques (vs baseline 2026-04-15)\n\n"
        "| Q# | Question | Avant Hit@5 | Avant Faith | Après Hit@5 | Après Faith |\n"
        "|---|---|---|---|---|---|"
    )
    by_id = {r["question"]["id"]: r for r in results}
    rows = [header]
    for qid, (h_before, f_before) in _BASELINE.items():
        r = by_id.get(qid)
        if r is None:
            rows.append(f"| {qid} | (non joué) | {h_before} | {f_before} | — | — |")
            continue
        if r["hit5"] is True:
            after = "1"
        elif r["hit5"] is False:
            after = "0"
        else:
            after = "—"
        short = r["question"]["question"][:50]
        rows.append(f"| {qid} | {short} | {h_before} | {f_before} | {after} | ? |")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Entry point helpers
# ---------------------------------------------------------------------------


def _build_meta(env_hash: str) -> dict:
    try:
        from src.settings import settings  # noqa: PLC0415

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "operator": "benchmark-script",
            "embedding": settings.embedding.model_name,
            "reranker": settings.reranker.model_name,
            "classifier": settings.classifier.model_name,
            "llm": settings.llm.hf_repo,
            "env_hash": env_hash,
        }
    except Exception:
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "operator": "benchmark-script",
            "embedding": "—",
            "reranker": "—",
            "classifier": "—",
            "llm": "—",
            "env_hash": env_hash,
        }


def _print_progress(result: BenchmarkResult, elapsed: float) -> None:
    q = result["question"]
    raw = result["raw"]
    if raw["error"] and not q["expect_422"]:
        print(f"ERROR {raw['error'][:50]}")
        return
    if q["expect_422"]:
        print("✅ 422" if raw["status_code"] == 422 else f"❌ {raw['status_code']}")
        return
    intent_ok = "✅" if result["intent_ok"] else "❌"
    if result["hit5"] is not None:
        hit5_icon = "✅" if result["hit5"] else "❌"
        hit5 = f" Hit@5={hit5_icon}"
    else:
        hit5 = ""
    print(f"{raw['intent']} {intent_ok}{hit5} ({elapsed:.1f}s)")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", default=_DEFAULT_URL, metavar="URL")
    parser.add_argument("--user", default=_DEFAULT_USER, metavar="USER")
    parser.add_argument("--password", default=_DEFAULT_PASSWORD, metavar="PASS")
    parser.add_argument("--limit", type=int, default=None, metavar="N")
    parser.add_argument("--question", default="", metavar="Q1,Q3")
    parser.add_argument("--output-dir", default=str(Path(__file__).parent), metavar="DIR")
    parser.add_argument("--env-file", default=".env", metavar="PATH")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = _parse_args()
    question_ids = [q.strip() for q in args.question.split(",") if q.strip()]

    questions = _load_questions(_FIXTURE)
    questions = _filter_questions(questions, args.limit, question_ids)

    print(f"Authenticating as {args.user} ...", flush=True)
    token = _authenticate(args.url, args.user, args.password)

    print("Warming up (2 requests) ...", flush=True)
    _warmup(args.url, token)

    results: list[BenchmarkResult] = []
    session_map: dict[str, str] = {}

    with httpx.Client(headers={"Authorization": f"Bearer {token}"}) as session:
        for i, q in enumerate(questions, 1):
            print(f"  [{i:02d}/{len(questions)}] {q['id']} ...", end=" ", flush=True)
            t0 = time.perf_counter()
            raw = _call_api(session, args.url, q, session_map, args.user, args.password)
            results.append(_evaluate(q, raw))
            _print_progress(results[-1], time.perf_counter() - t0)

    metrics = _compute_metrics(results)
    md = _render_markdown(results, metrics, _build_meta(_env_hash(Path(args.env_file))))
    out = Path(args.output_dir) / f"results_{datetime.now().strftime('%Y%m%d')}.md"
    out.write_text(md, encoding="utf-8")

    print(f"\nRapport : {out}")
    print(
        f"Intent  : {metrics['intent_ok']}/{metrics['intent_total']}  |  Hit@5 : {metrics['hit5_ok']}/{metrics['hit5_total']}"
    )


if __name__ == "__main__":
    main()
