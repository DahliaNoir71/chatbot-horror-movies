"""Language detector for query routing in the BM25 multilingual retriever.

Wraps `lingua-language-detector` (FR/EN) and exposes a single `detect()`
returning `'fr'`, `'en'` or `'mixed'`. The 'mixed' bucket triggers a
fallback strategy in the BM25 retriever (query both `tsvector_fr` and
`tsvector_en` columns) for ambiguous or code-switching queries like
*"je cherche un scary movie"*.

The underlying lingua detector is loaded once at import time — it
compiles a few MB of language profiles and is too expensive to rebuild
per request.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from lingua import Language, LanguageDetectorBuilder
from lingua import LanguageDetector as _LinguaDetector

# Confidence threshold above which we trust the dominant language.
# Below this, the query is treated as `mixed` so the retriever queries
# both tsvector columns instead of routing to a single one.
_CONFIDENCE_THRESHOLD = 0.7

# Single-token queries are inherently ambiguous — proper nouns like
# "Halloween" trigger a high lingua confidence but should fall back to
# 'mixed' so BM25 hits both FR and EN tsvector columns.
_MIN_TOKEN_COUNT = 2

DetectedLang = Literal["fr", "en", "mixed"]


@lru_cache(maxsize=1)
def _build_default_detector() -> _LinguaDetector:
    """Build the default FR/EN lingua detector (singleton, lru-cached)."""
    return LanguageDetectorBuilder.from_languages(
        Language.FRENCH,
        Language.ENGLISH,
    ).build()


class LanguageDetector:
    """Detect query language (FR / EN / mixed) for BM25 routing.

    Attributes:
        _detector: Underlying lingua-language-detector instance.
    """

    def __init__(self, detector: _LinguaDetector | None = None) -> None:
        """Initialize the detector.

        Args:
            detector: Optional pre-built lingua detector. When None, the
                shared default (FR + EN, lru-cached) is used.
        """
        self._detector = detector or _build_default_detector()

    def detect(self, query: str) -> DetectedLang:
        """Classify `query` as FR, EN or mixed.

        Returns 'fr' or 'en' only when the query has at least
        `_MIN_TOKEN_COUNT` tokens AND the dominant language confidence
        exceeds `_CONFIDENCE_THRESHOLD`. Otherwise returns 'mixed' so
        the BM25 retriever queries both tsvector columns.

        Args:
            query: User query text.

        Returns:
            One of 'fr', 'en', 'mixed'.
        """
        if not query or not query.strip():
            return "mixed"
        if len(query.split()) < _MIN_TOKEN_COUNT:
            return "mixed"

        scores: list[Any] = self._detector.compute_language_confidence_values(query)
        if not scores:
            return "mixed"

        top = scores[0]
        # `ConfidenceValue` exposes `.language` (Language enum) and `.value` (float)
        if top.value < _CONFIDENCE_THRESHOLD:
            return "mixed"
        return _language_to_code(top.language)


def _language_to_code(language: Language) -> DetectedLang:
    """Map a lingua `Language` enum to a 2-letter code."""
    if language == Language.FRENCH:
        return "fr"
    if language == Language.ENGLISH:
        return "en"
    return "mixed"
