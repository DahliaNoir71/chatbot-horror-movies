"""Tests that RAGPipeline feeds the reranker a wide candidate pool.

Regression guard for the rerank-pool-starvation bug: the async retriever must
be queried for `rerank_pool_top_k` candidates so the cross-encoder reranks a
wide pool, instead of re-scoring the 5 documents RRF already pre-selected.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.rag.pipeline import RAGPipeline
from src.settings.retrieval import RetrievalSettings


def _make_pipeline(pool: int) -> tuple[RAGPipeline, AsyncMock]:
    retriever = MagicMock()
    retriever.search = AsyncMock(return_value=[])

    reranker = MagicMock()
    reranker.rerank.return_value = []

    pipeline = RAGPipeline(
        retriever=retriever,
        reranker=reranker,
        llm_service=MagicMock(),
        retrieval_settings=RetrievalSettings(rerank_pool_top_k=pool, open_fallback_enabled=False),
    )
    return pipeline, retriever.search


class TestRAGPipelineRerankPool:
    @pytest.mark.unit
    async def test_execute_requests_rerank_pool_not_final_top_k(self) -> None:
        pipeline, search = _make_pipeline(pool=30)

        await pipeline.execute("rag", "body horror")

        search.assert_awaited_once_with("body horror", top_k=30)

    @pytest.mark.unit
    async def test_stream_requests_rerank_pool_not_final_top_k(self) -> None:
        pipeline, search = _make_pipeline(pool=25)

        await pipeline.execute_stream("rag", "body horror")

        search.assert_awaited_once_with("body horror", top_k=25)
