"""Generate consolidated MLOps evaluation report from pipeline artifacts.

Parses JUnit XML results from each job, reads custom JSON artifacts
(confusion matrix, embedding metrics), and generates a structured
markdown report.

Usage::

    uv run python scripts/mlops_report.py \\
        --artifacts-dir reports/ \\
        --output reports/mlops-report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree
from xml.etree.ElementTree import Element


# =========================================================================
# CLI
# =========================================================================


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate MLOps evaluation report",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        required=True,
        help="Root directory containing downloaded artifacts",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output markdown report path",
    )
    return parser.parse_args()


# =========================================================================
# JUnit XML parsing
# =========================================================================


def _parse_testcase_status(tc: Element) -> dict:
    """Extract status and optional message from a single <testcase>."""
    case: dict = {
        "name": tc.get("name", "unknown"),
        "classname": tc.get("classname", ""),
        "time": float(tc.get("time", 0)),
        "status": "passed",
    }
    failure = tc.find("failure")
    if failure is not None:
        case["status"] = "failed"
        case["message"] = failure.get("message", "")
        return case
    error = tc.find("error")
    if error is not None:
        case["status"] = "error"
        case["message"] = error.get("message", "")
        return case
    if tc.find("skipped") is not None:
        case["status"] = "skipped"
    return case


def _accumulate_suite(suite: Element) -> tuple[int, int, int, int, float, list[dict]]:
    """Extract totals and test cases from a single <testsuite>."""
    tests = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    elapsed = float(suite.get("time", 0))
    cases = [_parse_testcase_status(tc) for tc in suite.findall("testcase")]
    return tests, failures, errors, skipped, elapsed, cases


def _parse_junit_xml(xml_path: Path) -> dict:
    """Parse a JUnit XML file and return summary statistics."""
    if not xml_path.exists():
        return {"found": False, "error": f"File not found: {xml_path}"}

    tree = ElementTree.parse(xml_path)
    root = tree.getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]

    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    total_time = 0.0
    test_cases: list[dict] = []

    for suite in suites:
        tests, failures, errors, skipped, elapsed, cases = _accumulate_suite(suite)
        total_tests += tests
        total_failures += failures
        total_errors += errors
        total_skipped += skipped
        total_time += elapsed
        test_cases.extend(cases)

    return {
        "found": True,
        "tests": total_tests,
        "failures": total_failures,
        "errors": total_errors,
        "skipped": total_skipped,
        "time": round(total_time, 2),
        "passed": total_tests - total_failures - total_errors - total_skipped,
        "test_cases": test_cases,
    }


def _load_json(path: Path) -> dict | None:
    """Load a JSON artifact, returning *None* if the file does not exist."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# =========================================================================
# Report section builders
# =========================================================================


def _status_badge(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def _build_overview(results: dict[str, dict]) -> str:
    lines = [
        "## Overview\n",
        "| Component | Tests | Passed | Failed | Time | Status |",
        "|-----------|-------|--------|--------|------|--------|",
    ]
    for name, data in results.items():
        junit = data.get("junit", {})
        if not junit.get("found"):
            lines.append(f"| {name} | — | — | — | — | NO DATA |")
            continue
        status = _status_badge(junit["failures"] == 0 and junit["errors"] == 0)
        lines.append(
            f"| {name} | {junit['tests']} | {junit['passed']} | "
            f"{junit['failures']} | {junit['time']}s | {status} |"
        )
    lines.append("")
    return "\n".join(lines)


def _format_accuracy(accuracy: object) -> str:
    """Format an accuracy value (float or fallback) as a percentage string."""
    if isinstance(accuracy, float):
        return f"{accuracy:.1%}"
    return str(accuracy)


def _build_intent_table(per_intent: dict) -> list[str]:
    """Build the per-intent recall markdown table rows."""
    lines = [
        "| Intent | Recall | Correct / Total | Weak? |",
        "|--------|--------|-----------------|-------|",
    ]
    for intent, stats in per_intent.items():
        recall_pct = f"{stats['recall']:.1%}"
        weak = "Yes" if stats.get("is_weak") else ""
        lines.append(
            f"| {intent} | {recall_pct} | "
            f"{stats['correct']}/{stats['total']} | {weak} |"
        )
    lines.append("")
    return lines


def _build_intent_section(results: dict[str, dict]) -> str:
    lines = ["## Intent Classifier (DeBERTa-v3 zero-shot)\n"]

    confusion = results.get("intent-classifier", {}).get("confusion_matrix")
    if not confusion:
        lines.append("*Confusion matrix artifact not found.*\n")
        return "\n".join(lines)

    lines.append(f"**Overall Accuracy**: {_format_accuracy(confusion.get('overall_accuracy', 'N/A'))}")
    lines.append(f"**Total Cases**: {confusion.get('total_cases', 'N/A')}")
    lines.append(
        f"**Weak Intents** (known limitation): "
        f"{', '.join(confusion.get('weak_intents', []))}\n"
    )

    per_intent = confusion.get("per_intent", {})
    if per_intent:
        lines.extend(_build_intent_table(per_intent))

    return "\n".join(lines)


def _build_embedding_metrics(metrics: dict) -> list[str]:
    """Build the embedding validation and pair summary lines."""
    lines: list[str] = []

    validations = metrics.get("validations", {})
    if validations:
        lines.append("| Validation | Status | Failures |")
        lines.append("|------------|--------|----------|")
        for name, result in validations.items():
            lines.append(
                f"| {name} | {_status_badge(result['passed'])} | "
                f"{result['failures']} |"
            )
        lines.append("")

    for label, key in [("Similarity", "similarity_pairs"), ("Dissimilarity", "dissimilar_pairs")]:
        pairs = metrics.get(key, [])
        if pairs:
            passed = sum(1 for p in pairs if p["passed"])
            lines.append(f"**{label} pairs**: {passed}/{len(pairs)} passed")

    lines.append("")
    return lines


def _build_embedding_section(results: dict[str, dict]) -> str:
    lines = ["## Embedding Model (all-MiniLM-L6-v2)\n"]

    metrics = results.get("embeddings", {}).get("embedding_metrics")
    if not metrics:
        lines.append("*Embedding metrics artifact not found.*\n")
        return "\n".join(lines)

    lines.append(f"**Model**: {metrics.get('model_name', 'N/A')}")
    lines.append(f"**Dimension**: {metrics.get('expected_dimension', 'N/A')}")
    lines.append(f"**Texts Processed**: {metrics.get('total_texts', 'N/A')}")
    lines.append(
        f"**Performance**: {metrics.get('avg_time_per_text_ms', 'N/A')} ms/text "
        f"(individual), {metrics.get('batch_duration_seconds', 'N/A')}s (batch)\n"
    )
    lines.extend(_build_embedding_metrics(metrics))

    return "\n".join(lines)


def _build_rag_section(results: dict[str, dict]) -> str:
    lines = ["## RAG Response Quality\n"]

    junit = results.get("rag-evaluation", {}).get("junit", {})
    if not junit.get("found"):
        lines.append("*RAG evaluation results not found.*\n")
        return "\n".join(lines)

    lines.append(
        f"**Tests**: {junit['tests']} total, {junit['passed']} passed, "
        f"{junit['failures']} failed\n"
    )

    failures = [tc for tc in junit.get("test_cases", []) if tc["status"] == "failed"]
    if failures:
        lines.append("**Failed tests:**\n")
        for f in failures:
            msg = f.get("message", "no message")[:120]
            lines.append(f"- `{f['name']}`: {msg}")
        lines.append("")

    return "\n".join(lines)


def _build_thresholds_section() -> str:
    return "\n".join([
        "## Quality Thresholds\n",
        "| Metric | Threshold | Source |",
        "|--------|-----------|--------|",
        "| Overall intent accuracy | >= 55% | test_intent_accuracy.py |",
        "| Strong intent recall | >= 60% (4+ intents) | test_intent_accuracy.py |",
        "| Embedding dimension | = 384 | embedding_service.py |",
        "| Embedding L2 norm | ~1.0 (tol. 0.01) | test_embedding_quality.py |",
        "| Batch consistency | cosine sim > 0.99 | test_embedding_quality.py |",
        "| Data validation tests | 100% pass | test_data_validation.py |",
        "| Response quality tests | 100% pass | test_response_quality.py |",
        "",
    ])


# =========================================================================
# Pass/fail determination
# =========================================================================


def _check_all_passed(results: dict[str, dict]) -> bool:
    """Return *True* only when every job passed with no failures."""
    for data in results.values():
        junit = data.get("junit", {})
        if not junit.get("found"):
            return False
        if junit.get("failures", 0) > 0 or junit.get("errors", 0) > 0:
            return False

    emb_metrics = results.get("embeddings", {}).get("embedding_metrics")
    if emb_metrics and not emb_metrics.get("overall_passed", False):
        return False

    return True


# =========================================================================
# Main
# =========================================================================


def _collect_results(artifacts_dir: Path) -> dict[str, dict]:
    """Parse all job artifacts into a unified results dict."""
    job_dirs = {
        "validate-data": artifacts_dir / "validate-data-results",
        "intent-classifier": artifacts_dir / "intent-classifier-results",
        "embeddings": artifacts_dir / "embeddings-results",
        "rag-evaluation": artifacts_dir / "rag-evaluation-results",
    }

    results: dict[str, dict] = {}
    for job_name, job_dir in job_dirs.items():
        results[job_name] = {
            "junit": _parse_junit_xml(job_dir / "junit.xml"),
        }

    results["intent-classifier"]["confusion_matrix"] = _load_json(
        job_dirs["intent-classifier"] / "intent_confusion_matrix.json"
    )
    results["embeddings"]["embedding_metrics"] = _load_json(
        job_dirs["embeddings"] / "embedding_metrics.json"
    )
    return results


def _build_header(all_passed: bool) -> list[str]:
    """Build the report header with CI metadata."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    sha = os.environ.get("GITHUB_SHA", "unknown")[:8]
    ref = os.environ.get("GITHUB_REF", "unknown")
    repo = os.environ.get("GITHUB_REPOSITORY", "")

    overall_status = "ALL PASSED" if all_passed else "FAILURES DETECTED"
    run_line = (
        f"**Run**: [#{run_id}](https://github.com/{repo}/actions/runs/{run_id})"
        if repo
        else f"**Run**: #{run_id}"
    )

    return [
        "# MLOps Evaluation Report — HorrorBot\n",
        f"**Status**: {overall_status}",
        f"**Date**: {timestamp}",
        f"**Commit**: `{sha}`",
        f"**Branch**: `{ref}`",
        run_line,
        "",
        "---\n",
    ]


def main() -> int:
    args = _parse_args()

    results = _collect_results(args.artifacts_dir)
    all_passed = _check_all_passed(results)

    report = "\n".join([
        *_build_header(all_passed),
        _build_overview(results),
        _build_intent_section(results),
        _build_embedding_section(results),
        _build_rag_section(results),
        _build_thresholds_section(),
        "---",
        "*Report generated by `scripts/mlops_report.py`*",
    ])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Report written to: {args.output}")
    print(f"Overall status: {'ALL PASSED' if all_passed else 'FAILURES DETECTED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
