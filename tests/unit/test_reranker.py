"""Unit tests for RerankerService.

Tests reranking logic with a mocked CrossEncoder model.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

from src.services.rag.reranker import RerankerService
from src.services.rag.retriever import RetrievedDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(content: str, similarity: float = 0.5) -> RetrievedDocument:
    """Create a minimal RetrievedDocument for testing."""
    return RetrievedDocument(
        id=uuid4(),
        content=content,
        source_type="film_overview",
        source_id=1,
        metadata={"title": "Test"},
        similarity=similarity,
    )


def _make_reranker(
    top_k: int = 5,
    min_score: float = -8.0,
) -> RerankerService:
    """Create a RerankerService with mocked model."""
    service = RerankerService(
        model_name="mock-model",
        top_k=top_k,
        min_score=min_score,
    )
    service._model = MagicMock()
    return service


# =========================================================================
# Tests
# =========================================================================


class TestRerankerService:
    """Unit tests for RerankerService."""

    @staticmethod
    def test_empty_documents_returns_empty():
        """Reranking empty list returns empty list."""
        service = _make_reranker()
        result = service.rerank("test query", [])
        assert result == []

    @staticmethod
    def test_rerank_reorders_documents():
        """Documents are reordered by cross-encoder score."""
        service = _make_reranker(top_k=3)
        docs = [_make_doc("low"), _make_doc("high"), _make_doc("mid")]

        # Cross-encoder scores: low=0.1, high=0.9, mid=0.5
        service._model.predict.return_value = np.array([0.1, 0.9, 0.5])

        result = service.rerank("test query", docs)

        assert len(result) == 3
        assert result[0].content == "high"
        assert result[1].content == "mid"
        assert result[2].content == "low"

    @staticmethod
    def test_top_k_limits_results():
        """Only top_k documents are returned."""
        service = _make_reranker(top_k=2)
        docs = [_make_doc(f"doc{i}") for i in range(5)]

        service._model.predict.return_value = np.array([0.5, 0.9, 0.1, 0.8, 0.3])

        result = service.rerank("test query", docs)

        assert len(result) == 2

    @staticmethod
    def test_min_score_filters_documents():
        """Documents below min_score are filtered out."""
        service = _make_reranker(top_k=5, min_score=0.0)
        docs = [_make_doc("good"), _make_doc("bad"), _make_doc("ok")]

        service._model.predict.return_value = np.array([0.5, -1.0, 0.2])

        result = service.rerank("test query", docs)

        assert len(result) == 2
        assert all(doc.content != "bad" for doc in result)

    @staticmethod
    def test_all_below_min_score_returns_empty():
        """If all documents are below min_score, return empty list."""
        service = _make_reranker(top_k=5, min_score=5.0)
        docs = [_make_doc("doc1"), _make_doc("doc2")]

        service._model.predict.return_value = np.array([0.1, 0.2])

        result = service.rerank("test query", docs)

        assert result == []

    @staticmethod
    def test_pairs_passed_to_model():
        """Correct (query, content) pairs are passed to the model."""
        service = _make_reranker()
        docs = [_make_doc("content A"), _make_doc("content B")]

        service._model.predict.return_value = np.array([0.5, 0.5])

        service.rerank("my query", docs)

        call_args = service._model.predict.call_args[0][0]
        assert call_args == [("my query", "content A"), ("my query", "content B")]
