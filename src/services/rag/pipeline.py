"""RAG pipeline orchestrating retrieval, prompt building, and LLM generation.

Combines DocumentRetriever, RAGPromptBuilder, and LLMService
into a single pipeline for RAG-based intents.
"""

import asyncio
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from src.etl.utils.logger import setup_logger
from src.monitoring.metrics import (
    LLM_PROMPT_TOKENS,
    LLM_REQUEST_DURATION,
    LLM_REQUESTS_TOTAL,
    LLM_TOKENS_GENERATED,
    LLM_TOKENS_PER_SECOND,
    RAG_NO_CONTEXT_RESPONSES_TOTAL,
)
from src.services.llm.llm_service import LLMService, get_llm_service
from src.services.rag.hybrid_retriever import HybridRetriever, get_hybrid_retriever
from src.services.rag.prompt_builder import RAGPromptBuilder
from src.services.rag.reranker import RerankerService, get_reranker_service
from src.services.rag.retriever import DocumentRetriever, RetrievedDocument
from src.settings import settings
from src.settings.retrieval import RetrievalSettings

logger = setup_logger("services.rag.pipeline")


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class RAGResult:
    """Result from a RAG pipeline execution.

    Attributes:
        text: Generated response text.
        intent: The intent that triggered this pipeline.
        documents: Retrieved documents used as context.
        usage: Token usage stats from LLM.
        retrieval_time_ms: Time spent on vector retrieval.
        rerank_time_ms: Time spent on cross-encoder reranking.
        generation_time_ms: Time spent on LLM generation.
    """

    text: str
    intent: str
    documents: list[RetrievedDocument] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    retrieval_time_ms: float = 0.0
    rerank_time_ms: float = 0.0
    generation_time_ms: float = 0.0


# =============================================================================
# RAG PIPELINE
# =============================================================================


class RAGPipeline:
    """Full RAG pipeline: retrieve -> rerank -> build prompt -> generate.

    Attributes:
        _retriever: Retriever exposing `.retrieve(query) -> list[RetrievedDocument]`.
            Defaults to the hybrid (vector + BM25 + popularity) retriever.
        _reranker: Cross-encoder reranker for precision filtering.
        _llm: LLM service for text generation.
    """

    def __init__(
        self,
        retriever: HybridRetriever | DocumentRetriever | None = None,
        reranker: RerankerService | None = None,
        llm_service: LLMService | None = None,
        retrieval_settings: RetrievalSettings | None = None,
    ) -> None:
        """Initialize pipeline with injectable dependencies.

        Args:
            retriever: Override retriever (for testing). Accepts any object
                exposing `.retrieve(query, match_count=...)` — the shared
                interface of `HybridRetriever` (sync adapter) and
                `DocumentRetriever`.
            reranker: Override reranker service (for testing).
            llm_service: Override LLM service (for testing).
            retrieval_settings: Override retrieval settings (for testing).
        """
        self._retriever = retriever or get_hybrid_retriever()
        self._reranker = reranker or get_reranker_service()
        self._llm = llm_service or get_llm_service()
        self._settings = retrieval_settings or settings.retrieval
        self._logger = logger

    async def execute(
        self,
        intent: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> RAGResult:
        """Execute full RAG pipeline.

        Retrieval is awaited directly (async). CPU-bound rerank + LLM
        steps run via `asyncio.to_thread` so they don't block the loop.

        Args:
            intent: Classified intent.
            user_message: Current user query.
            history: Conversation history.

        Returns:
            RAGResult with generated text and metadata.
        """
        retrieval_start = time.perf_counter()
        documents = await self._retrieve(user_message)
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

        rerank_start = time.perf_counter()
        documents = await asyncio.to_thread(self._reranker.rerank, user_message, documents)
        rerank_ms = (time.perf_counter() - rerank_start) * 1000

        trusted_docs = [
            d
            for d in documents
            if d.rerank_score is None or d.rerank_score >= self._settings.min_rerank_score
        ]

        if not trusted_docs:
            RAG_NO_CONTEXT_RESPONSES_TOTAL.inc()
            return self._build_no_context_response(intent)

        messages = RAGPromptBuilder.build(
            intent=intent,
            user_message=user_message,
            documents=trusted_docs,
            history=history,
        )

        gen_start = time.perf_counter()
        try:
            result = await asyncio.to_thread(self._llm.generate_chat, messages)
            gen_ms = (time.perf_counter() - gen_start) * 1000

            self._record_llm_metrics(result.get("usage", {}), gen_ms / 1000)
            LLM_REQUESTS_TOTAL.labels(status="success").inc()

            self._logger.info(
                f"RAG pipeline complete: "
                f"retrieval={round(retrieval_ms)}ms, "
                f"rerank={round(rerank_ms)}ms ({len(trusted_docs)} docs), "
                f"generation={round(gen_ms)}ms, "
                f"tokens={result.get('usage', {}).get('completion_tokens', '?')}, "
                f"total={round(retrieval_ms + rerank_ms + gen_ms)}ms"
            )

            return RAGResult(
                text=result["text"],
                intent=intent,
                documents=trusted_docs,
                usage=result.get("usage", {}),
                retrieval_time_ms=retrieval_ms,
                rerank_time_ms=rerank_ms,
                generation_time_ms=gen_ms,
            )
        except Exception:
            LLM_REQUESTS_TOTAL.labels(status="error").inc()
            raise

    async def execute_stream(
        self,
        intent: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[Iterator[str], list[RetrievedDocument]]:
        """Execute RAG pipeline with streaming LLM output.

        Retrieval + rerank are async; the returned LLM token iterator is
        sync (consumed downstream by the SSE generator, which runs in
        Starlette's thread pool so the event loop stays free).

        Args:
            intent: Classified intent.
            user_message: Current user query.
            history: Conversation history.

        Returns:
            Tuple of (token iterator, retrieved documents).
        """
        documents = await self._retrieve(user_message)
        documents = await asyncio.to_thread(self._reranker.rerank, user_message, documents)

        self._logger.info(
            f"RAG stream retrieval: "
            f"{len(documents)} docs after rerank "
            f"(top_similarity={round(documents[0].similarity, 3) if documents else 'N/A'}, "
            f"top_rerank={round(documents[0].rerank_score, 3) if documents and documents[0].rerank_score else 'N/A'})"
        )

        messages = RAGPromptBuilder.build(
            intent=intent,
            user_message=user_message,
            documents=documents,
            history=history,
        )

        token_stream = self._llm.generate_stream(messages)
        return token_stream, documents

    async def _retrieve(self, user_message: str) -> list[RetrievedDocument]:
        """Dispatch to the retriever's async `search()` or sync `retrieve()`.

        `HybridRetriever` exposes an async `search()`; legacy/test mocks
        expose only sync `retrieve()`. The sync path is bridged via
        `asyncio.to_thread` so neither blocks the event loop.
        """
        search = getattr(self._retriever, "search", None)
        if search is not None and asyncio.iscoroutinefunction(search):
            return await search(user_message)
        return await asyncio.to_thread(self._retriever.retrieve, user_message)

    def _build_no_context_response(self, intent: str) -> RAGResult:
        """Build response when no document passed rerank confidence threshold.

        This is the anti-hallucination circuit breaker: when the retriever
        fails to find grounded context, we refuse to answer rather than let
        the LLM fabricate from pre-training.

        Args:
            intent: The intent that triggered this pipeline execution.

        Returns:
            RAGResult with a templated refusal message and no documents.
        """
        return RAGResult(
            text=(
                "Je n'ai pas trouvé d'information fiable dans ma base de films "
                "sur ce sujet. Peux-tu reformuler ou préciser ta question ?"
            ),
            intent=intent,
        )

    @staticmethod
    def _record_llm_metrics(usage: dict[str, Any], duration_s: float) -> None:
        """Record LLM performance metrics.

        Args:
            usage: Token usage stats from LLM.
            duration_s: Generation duration in seconds.
        """
        LLM_REQUEST_DURATION.observe(duration_s)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        if prompt_tokens:
            LLM_PROMPT_TOKENS.inc(prompt_tokens)
        if completion_tokens:
            LLM_TOKENS_GENERATED.inc(completion_tokens)
            if duration_s > 0:
                LLM_TOKENS_PER_SECOND.set(completion_tokens / duration_s)
