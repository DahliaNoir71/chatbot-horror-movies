"""T1 — Intent classifier accuracy tests with confusion matrix.

Runs the real DeBERTa-v3 zero-shot classifier against 50+ labeled queries.
Computes overall accuracy, per-intent recall, and generates a confusion matrix.

With 3 well-separated intents (needs_database, conversational, off_topic),
accuracy should be significantly higher than the previous 7-label setup.

Requires: ``ml`` dependency group (transformers, torch).
Run with: ``uv run --group ml pytest tests/model/test_intent_accuracy.py -m model -v``
"""

from __future__ import annotations

import json
from collections import defaultdict

import pytest

from src.services.intent.classifier import INTENT_LABELS

# ---------------------------------------------------------------------------
# Thresholds calibrated against real model behavior
# ---------------------------------------------------------------------------

# Overall accuracy target (3 well-separated labels -> much better than 7).
MINIMUM_OVERALL_ACCURACY = 0.75

# Per-intent minimum recall -- all intents should be "strong" with 3 labels.
STRONG_INTENT_MIN_RECALL = 0.60

# All 3 intents must meet the recall threshold.
MIN_STRONG_INTENTS_PASSING = 3


# =========================================================================
# T1 -- Intent accuracy on labeled dataset
# =========================================================================


@pytest.mark.model
@pytest.mark.slow
class TestIntentAccuracy:
    """T1 -- Confusion matrix on 50+ labeled queries."""

    @staticmethod
    def test_overall_accuracy(intent_predictions):
        """Overall accuracy >= 75% across all test cases."""
        correct = sum(1 for p in intent_predictions if p["predicted"] == p["expected"])
        accuracy = correct / len(intent_predictions)
        failures = [p for p in intent_predictions if p["predicted"] != p["expected"]]

        assert accuracy >= MINIMUM_OVERALL_ACCURACY, (
            f"Overall accuracy {accuracy:.2%} < {MINIMUM_OVERALL_ACCURACY:.0%} "
            f"({correct}/{len(intent_predictions)}). "
            f"Failures:\n"
            + "\n".join(
                f"  - \"{f['query']}\" expected={f['expected']} got={f['predicted']} "
                f"(conf={f['confidence']:.3f})"
                for f in failures
            )
        )

    @staticmethod
    def test_per_intent_recall(intent_predictions):
        """All 3 intents achieve recall >= 60%."""
        by_intent = defaultdict(lambda: {"total": 0, "correct": 0})

        for p in intent_predictions:
            by_intent[p["expected"]]["total"] += 1
            if p["predicted"] == p["expected"]:
                by_intent[p["expected"]]["correct"] += 1

        passing = 0
        failing = []
        for intent, stats in by_intent.items():
            recall = stats["correct"] / stats["total"]
            if recall >= STRONG_INTENT_MIN_RECALL:
                passing += 1
            else:
                failing.append(f"  {intent}: {recall:.2%} ({stats['correct']}/{stats['total']})")

        assert passing >= MIN_STRONG_INTENTS_PASSING, (
            f"Only {passing} intents pass >= {STRONG_INTENT_MIN_RECALL:.0%} recall "
            f"(need {MIN_STRONG_INTENTS_PASSING}). Failing:\n"
            + "\n".join(failing)
        )

    @staticmethod
    def test_confidence_above_threshold_for_correct(intent_predictions):
        """Correctly classified cases have confidence >= 0.3.

        The classifier falls back to ``needs_database`` when
        confidence < 0.4. Some queries are *correctly* classified via this
        fallback. We use 0.3 as the test threshold to allow for these.
        """
        low_confidence = [
            p for p in intent_predictions
            if p["predicted"] == p["expected"] and p["confidence"] < 0.3
        ]

        assert len(low_confidence) == 0, (
            f"{len(low_confidence)} correctly classified queries have confidence < 0.3:\n"
            + "\n".join(
                f"  - \"{c['query']}\" ({c['predicted']}, conf={c['confidence']:.3f})"
                for c in low_confidence
            )
        )

    @staticmethod
    def test_all_scores_contain_all_labels(intent_predictions):
        """The all_scores dict contains scores for every defined intent label."""
        sample = intent_predictions[0]

        for label in INTENT_LABELS:
            assert label in sample["all_scores"], (
                f"Label '{label}' missing from all_scores"
            )

    @staticmethod
    def test_confusion_matrix_generated(intent_predictions, artifact_dir):
        """Generate and save a confusion matrix as JSON artifact."""
        labels = sorted(set(INTENT_LABELS))
        matrix = {actual: dict.fromkeys(labels, 0) for actual in labels}
        for p in intent_predictions:
            if p["expected"] in matrix and p["predicted"] in matrix[p["expected"]]:
                matrix[p["expected"]][p["predicted"]] += 1

        report = {
            "confusion_matrix": matrix,
            "per_intent": {},
            "total_cases": len(intent_predictions),
        }
        total_correct = 0
        for intent in labels:
            tp = matrix[intent][intent]
            total = sum(matrix[intent].values())
            total_correct += tp
            report["per_intent"][intent] = {
                "total": total,
                "correct": tp,
                "recall": round(tp / total, 3) if total > 0 else 0.0,
            }
        report["overall_accuracy"] = round(total_correct / len(intent_predictions), 3)

        # Save artifact
        report_path = artifact_dir / "intent_confusion_matrix.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        assert report_path.exists()

        # Log summary for test output
        print("\n=== Intent Accuracy Report ===")
        print(f"Overall accuracy: {report['overall_accuracy']:.1%}")
        for intent, stats in report["per_intent"].items():
            print(f"  {intent}: {stats['recall']:.1%} ({stats['correct']}/{stats['total']})")
