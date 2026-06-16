"""Tests for the open-knowledge fallback.

When retrieval returns nothing trusted, the pipeline either answers from the
LLM's general knowledge with an explicit "not from my database" prefix
(open_fallback_enabled=True) or returns the strict templated refusal (False).
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.services.rag.pipeline import _OPEN_FALLBACK_PREFIX, RAGPipeline
from src.services.rag.retriever import RetrievedDocument
from src.settings.retrieval import RetrievalSettings


def _below_threshold_doc() -> RetrievedDocument:
    # rerank_score -9.0 < min_rerank_score -5.0 → filtered out → no trusted docs.
    return RetrievedDocument(
        id=uuid4(),
        content="x",
        source_type="film_overview",
        source_id=1,
        metadata={},
        similarity=0.5,
        rerank_score=-9.0,
    )


def _make_pipeline(*, enabled: bool) -> tuple[RAGPipeline, MagicMock]:
    retriever = MagicMock()
    retriever.retrieve.return_value = [_below_threshold_doc()]

    reranker = MagicMock()
    reranker.rerank.return_value = [_below_threshold_doc()]

    llm = MagicMock()
    llm.generate_chat.return_value = {
        "text": "Le slasher s'impose en 1978 avec Halloween de John Carpenter.",
        "usage": {},
    }
    llm.generate_stream.return_value = iter(["Le ", "slasher."])

    settings = RetrievalSettings(min_rerank_score=-5.0, open_fallback_enabled=enabled)
    pipeline = RAGPipeline(
        retriever=retriever,
        reranker=reranker,
        llm_service=llm,
        retrieval_settings=settings,
    )
    return pipeline, llm


class TestOpenFallback:
    @pytest.mark.unit
    async def test_enabled_answers_from_llm_with_disclaimer(self) -> None:
        pipeline, llm = _make_pipeline(enabled=True)

        result = await pipeline.execute("needs_database", "histoire du slasher ?")

        llm.generate_chat.assert_called_once()
        assert result.text.startswith(_OPEN_FALLBACK_PREFIX)
        assert "Halloween" in result.text
        assert result.documents == []

    @pytest.mark.unit
    async def test_disabled_refuses_without_calling_llm(self) -> None:
        pipeline, llm = _make_pipeline(enabled=False)

        result = await pipeline.execute("needs_database", "histoire du slasher ?")

        llm.generate_chat.assert_not_called()
        assert "reformuler" in result.text
        assert not result.text.startswith(_OPEN_FALLBACK_PREFIX)

    @pytest.mark.unit
    async def test_stream_enabled_prefixes_disclaimer_then_tokens(self) -> None:
        pipeline, llm = _make_pipeline(enabled=True)

        token_stream, documents = await pipeline.execute_stream(
            "needs_database", "histoire du slasher ?"
        )
        chunks = list(token_stream)

        assert chunks[0] == _OPEN_FALLBACK_PREFIX
        assert "".join(chunks[1:]) == "Le slasher."
        assert documents == []
        llm.generate_stream.assert_called_once()
