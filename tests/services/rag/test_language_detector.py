"""Unit + perf tests for LanguageDetector (FR/EN/mixed routing)."""

from __future__ import annotations

import time

import pytest

from src.services.rag.language_detector import LanguageDetector


@pytest.fixture(scope="module")
def detector() -> LanguageDetector:
    """Module-scoped detector — lingua model load is too slow per test."""
    return LanguageDetector()


class TestDetect:
    """`LanguageDetector.detect` returns one of fr / en / mixed."""

    @staticmethod
    def test_french_query(detector: LanguageDetector) -> None:
        assert detector.detect("Recommande-moi un film de vampire des années 80") == "fr"

    @staticmethod
    def test_english_query(detector: LanguageDetector) -> None:
        assert detector.detect("Recommend a vampire movie from the 80s") == "en"

    @staticmethod
    def test_mixed_code_switching(detector: LanguageDetector) -> None:
        result = detector.detect("Je cherche un scary movie avec un masked killer")
        assert result == "mixed"

    @staticmethod
    def test_ambiguous_single_token(detector: LanguageDetector) -> None:
        # Proper noun shared between FR/EN — confidence drops below threshold.
        assert detector.detect("Halloween") == "mixed"

    @staticmethod
    def test_empty_string_does_not_crash(detector: LanguageDetector) -> None:
        assert detector.detect("") == "mixed"
        assert detector.detect("   ") == "mixed"


class TestPerformance:
    """Latency budget — 100 short queries must run under 5 seconds total."""

    @staticmethod
    def test_100_queries_under_5_seconds(detector: LanguageDetector) -> None:
        queries = [
            "Recommande-moi un film d'horreur",
            "I want a scary movie",
            "Halloween",
            "Films de vampire des années 80",
            "vampire films from the 80s",
        ] * 20  # 100 queries

        start = time.perf_counter()
        for q in queries:
            detector.detect(q)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"100 queries took {elapsed:.2f}s (>5s budget)"
