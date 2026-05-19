"""Tests for RAGPipeline rerank confidence threshold (anti-hallucination circuit breaker)."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.services.rag.pipeline import RAGPipeline
from src.services.rag.retriever import RetrievedDocument
from src.settings.retrieval import RetrievalSettings


def _make_doc(rerank_score: float) -> RetrievedDocument:
    return RetrievedDocument(
        id=uuid4(),
        content="horror film content",
        source_type="film_overview",
        source_id=1,
        metadata={},
        similarity=0.8,
        rerank_score=rerank_score,
    )


def _make_pipeline(
    reranked_docs: list[RetrievedDocument],
    min_score: float = -2.0,
) -> tuple[RAGPipeline, MagicMock]:
    retriever = MagicMock()
    retriever.retrieve.return_value = [_make_doc(0.0)]

    reranker = MagicMock()
    reranker.rerank.return_value = reranked_docs

    llm = MagicMock()
    llm.generate_chat.return_value = {"text": "LLM response", "usage": {}}

    retrieval_settings = RetrievalSettings(min_rerank_score=min_score)

    pipeline = RAGPipeline(
        retriever=retriever,
        reranker=reranker,
        llm_service=llm,
        retrieval_settings=retrieval_settings,
    )
    return pipeline, llm


class TestRAGPipelineRerankThreshold:
    @pytest.mark.unit
    async def test_all_below_threshold_returns_no_context(self) -> None:
        docs = [_make_doc(-3.0), _make_doc(-2.5), _make_doc(-2.1)]
        pipeline, llm = _make_pipeline(docs, min_score=-2.0)

        result = await pipeline.execute("rag", "scary movie")

        assert "reformuler" in result.text
        llm.generate_chat.assert_not_called()

    @pytest.mark.unit
    async def test_mixed_filters_low_confidence(self) -> None:
        docs = [_make_doc(-3.0), _make_doc(-1.0), _make_doc(0.0)]
        pipeline, llm = _make_pipeline(docs, min_score=-2.0)

        result = await pipeline.execute("rag", "scary movie")

        assert len(result.documents) == 2
        assert all(
            d.rerank_score is not None and d.rerank_score >= -2.0
            for d in result.documents
        )
        llm.generate_chat.assert_called_once()

    @pytest.mark.unit
    async def test_all_above_threshold_unchanged(self) -> None:
        docs = [_make_doc(0.5), _make_doc(1.0), _make_doc(-1.5)]
        pipeline, llm = _make_pipeline(docs, min_score=-2.0)

        result = await pipeline.execute("rag", "scary movie")

        assert len(result.documents) == 3
        llm.generate_chat.assert_called_once()

    @pytest.mark.unit
    async def test_metric_incremented(self) -> None:
        docs = [_make_doc(-5.0)]
        pipeline, _llm = _make_pipeline(docs, min_score=-2.0)

        with patch("src.services.rag.pipeline.RAG_NO_CONTEXT_RESPONSES_TOTAL") as mock_counter:
            await pipeline.execute("rag", "scary movie")
            mock_counter.inc.assert_called_once()
