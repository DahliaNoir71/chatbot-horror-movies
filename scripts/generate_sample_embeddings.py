"""Generate sample embeddings and validate model output quality.

This is the "training equivalent" step in the HorrorBot MLOps pipeline.
Since all models are pre-trained (zero-shot), embedding generation from
text data is the functional equivalent of training.

This script:
1. Loads the embedding model (all-MiniLM-L6-v2)
2. Generates embeddings for all fixture texts (individual + batch)
3. Validates dimension, normalization, batch consistency, non-zero output
4. Computes similarity/dissimilarity pair scores
5. Writes ``embedding_metrics.json`` artifact

Usage::

    uv run --group ml python scripts/generate_sample_embeddings.py \\
        --output-dir reports/embeddings \\
        --fixtures-dir tests/fixtures
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path



def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate sample embeddings and validate quality",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for output metrics JSON",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        required=True,
        help="Directory containing test fixture JSON files",
    )
    return parser.parse_args()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ------------------------------------------------------------------
# Fixture loading
# ------------------------------------------------------------------


def _collect_fixture_texts(fixtures_dir: Path) -> tuple[list[str], dict]:
    """Load fixture files and collect all unique texts to embed."""
    rag_data = json.loads(
        (fixtures_dir / "rag_test_queries.json").read_text(encoding="utf-8")
    )
    intent_cases = json.loads(
        (fixtures_dir / "intent_test_cases.json").read_text(encoding="utf-8")
    )

    texts: set[str] = set()
    for key in ("similarity_pairs", "dissimilar_pairs"):
        for pair in rag_data.get(key, []):
            texts.add(pair["query_a"])
            texts.add(pair["query_b"])
    for q in rag_data.get("quality_questions", []):
        texts.add(q["query"])
    for case in intent_cases:
        texts.add(case["query"])

    return sorted(texts), rag_data


# ------------------------------------------------------------------
# Embedding generation
# ------------------------------------------------------------------


def _generate_all(service, sorted_texts: list[str]) -> tuple[dict, list, float, float]:
    """Generate embeddings individually and in batch, return both with timings."""
    start = time.perf_counter()
    individual = {text: service.generate(text) for text in sorted_texts}
    individual_duration = time.perf_counter() - start

    start_batch = time.perf_counter()
    batch = service.generate_batch(sorted_texts)
    batch_duration = time.perf_counter() - start_batch

    return individual, batch, individual_duration, batch_duration


# ------------------------------------------------------------------
# Validation checks
# ------------------------------------------------------------------


def _check_dimensions(individual: dict, expected_dim: int) -> tuple[dict, str | None]:
    """Verify all vectors have the expected dimension."""
    failures = sum(1 for v in individual.values() if len(v) != expected_dim)
    result = {"passed": failures == 0, "failures": failures}
    error = f"Dimension mismatch: {failures} vectors != {expected_dim}" if failures else None
    return result, error


def _check_normalization(individual: dict) -> tuple[dict, str | None]:
    """Verify all non-zero vectors are L2-normalized."""
    failures = 0
    for vec in individual.values():
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0 and abs(norm - 1.0) > 0.01:
            failures += 1
    result = {"passed": failures == 0, "failures": failures}
    error = f"Normalization: {failures} vectors not L2-normalized" if failures else None
    return result, error


def _check_batch_consistency(
    individual: dict, batch: list, sorted_texts: list[str],
) -> tuple[dict, str | None]:
    """Verify batch embeddings match individually-generated ones."""
    failures = sum(
        1
        for i, text in enumerate(sorted_texts)
        if _cosine_similarity(individual[text], batch[i]) < 0.99
    )
    result = {"passed": failures == 0, "failures": failures}
    error = f"Batch consistency: {failures} mismatches" if failures else None
    return result, error


def _check_non_zero(individual: dict) -> tuple[dict, str | None]:
    """Verify non-empty texts produce non-zero vectors."""
    failures = sum(
        1
        for t, v in individual.items()
        if t.strip() and all(abs(x) < 1e-9 for x in v)
    )
    result = {"passed": failures == 0, "failures": failures}
    error = f"Zero vectors for {failures} non-empty texts" if failures else None
    return result, error


def _run_validations(
    individual: dict, batch: list, sorted_texts: list[str], expected_dim: int,
) -> tuple[dict[str, dict], list[str]]:
    """Run all validation checks and return results + errors."""
    checks = [
        ("dimension_check", _check_dimensions(individual, expected_dim)),
        ("normalization_check", _check_normalization(individual)),
        ("batch_consistency", _check_batch_consistency(individual, batch, sorted_texts)),
        ("non_zero_check", _check_non_zero(individual)),
    ]
    validations = {}
    errors = []
    for name, (result, error) in checks:
        validations[name] = result
        if error:
            errors.append(error)
    return validations, errors


# ------------------------------------------------------------------
# Pair similarity scoring
# ------------------------------------------------------------------


def _score_similarity_pairs(
    individual: dict, pairs: list[dict], *, min_threshold: bool,
) -> list[dict]:
    """Score similarity or dissimilarity pairs against their thresholds."""
    key = "expected_min_similarity" if min_threshold else "expected_max_similarity"
    results = []
    for pair in pairs:
        sim = _cosine_similarity(
            individual[pair["query_a"]], individual[pair["query_b"]]
        )
        threshold = pair[key]
        passed = sim >= threshold if min_threshold else sim <= threshold
        results.append({
            "query_a": pair["query_a"],
            "query_b": pair["query_b"],
            "similarity": round(sim, 4),
            "threshold": threshold,
            "passed": passed,
        })
    return results


# ------------------------------------------------------------------
# Summary printing
# ------------------------------------------------------------------


def _print_summary(
    service,
    expected_dim: int,
    num_texts: int,
    individual_duration: float,
    batch_duration: float,
    validations: dict,
    sim_pairs: list[dict],
    dissim_pairs: list[dict],
    errors: list[str],
) -> None:
    """Print human-readable summary to stdout."""
    print(f"\n{'=' * 55}")
    print("  Embedding Generation Report")
    print(f"{'=' * 55}")
    print(f"  Model:      {service.model_name}")
    print(f"  Dimension:  {expected_dim}")
    print(f"  Texts:      {num_texts}")
    print(
        f"  Duration:   {individual_duration:.2f}s (individual), "
        f"{batch_duration:.2f}s (batch)"
    )
    for name, result in validations.items():
        status = (
            "PASS" if result["passed"] else f"FAIL ({result['failures']} failures)"
        )
        print(f"  {name}: {status}")

    sim_passed = sum(1 for p in sim_pairs if p["passed"])
    dissim_passed = sum(1 for p in dissim_pairs if p["passed"])
    print(f"  Similarity pairs:    {sim_passed}/{len(sim_pairs)} passed")
    print(f"  Dissimilarity pairs: {dissim_passed}/{len(dissim_pairs)} passed")

    if errors:
        print(f"\n  FAILED: {len(errors)} validation error(s)")
        for err in errors:
            print(f"    - {err}")
    else:
        print("\n  All validations passed.")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> int:
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    sorted_texts, rag_data = _collect_fixture_texts(args.fixtures_dir)
    print(f"Collected {len(sorted_texts)} unique texts to embed")

    from src.services.embedding.embedding_service import (
        EMBEDDING_DIMENSION,
        EmbeddingService,
    )

    service = EmbeddingService()
    print(f"Model: {service.model_name}, Expected dimension: {EMBEDDING_DIMENSION}")

    individual, batch, ind_dur, batch_dur = _generate_all(service, sorted_texts)
    print(f"Individual: {len(sorted_texts)} texts in {ind_dur:.2f}s")
    print(f"Batch:      {len(sorted_texts)} texts in {batch_dur:.2f}s")

    validations, errors = _run_validations(
        individual, batch, sorted_texts, EMBEDDING_DIMENSION,
    )
    sim_pairs = _score_similarity_pairs(
        individual, rag_data.get("similarity_pairs", []), min_threshold=True,
    )
    dissim_pairs = _score_similarity_pairs(
        individual, rag_data.get("dissimilar_pairs", []), min_threshold=False,
    )

    all_passed = len(errors) == 0
    metrics = {
        "model_name": service.model_name,
        "expected_dimension": EMBEDDING_DIMENSION,
        "total_texts": len(sorted_texts),
        "individual_duration_seconds": round(ind_dur, 3),
        "batch_duration_seconds": round(batch_dur, 3),
        "avg_time_per_text_ms": round((ind_dur / len(sorted_texts)) * 1000, 2),
        "validations": validations,
        "similarity_pairs": sim_pairs,
        "dissimilar_pairs": dissim_pairs,
        "overall_passed": all_passed,
        "errors": errors,
    }

    output_path = args.output_dir / "embedding_metrics.json"
    output_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    _print_summary(
        service, EMBEDDING_DIMENSION, len(sorted_texts),
        ind_dur, batch_dur, validations, sim_pairs, dissim_pairs, errors,
    )
    print(f"  Metrics written to: {output_path}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
