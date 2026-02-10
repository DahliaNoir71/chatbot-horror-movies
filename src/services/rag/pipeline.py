"""RAG pipeline orchestrating retrieval, prompt building, and LLM generation.

Combines DocumentRetriever, RAGPromptBuilder, and LLMService
into a single pipeline for RAG-based intents.
"""

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
)
from src.services.llm.llm_service import LLMService, get_llm_service
from src.services.rag.prompt_builder import RAGPromptBuilder
from src.services.rag.retriever import (
    DocumentRetriever,
    RetrievedDocument,
    get_document_retriever,
)

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
        retrieval_time_ms: Time spent on document retrieval.
        generation_time_ms: Time spent on LLM generation.
    """

    text: str
    intent: str
    documents: list[RetrievedDocument] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    retrieval_time_ms: float = 0.0
    generation_time_ms: float = 0.0


# =============================================================================
# RAG PIPELINE
# =============================================================================


class RAGPipeline:
    """Full RAG pipeline: retrieve -> build prompt -> generate.

    Attributes:
        _retriever: Document retriever for vector search.
        _llm: LLM service for text generation.
    """

    def __init__(
        self,
        retriever: DocumentRetriever | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize pipeline with injectable dependencies.

        Args:
            retriever: Override document retriever (for testing).
            llm_service: Override LLM service (for testing).
        """
        self._retriever = retriever or get_document_retriever()
        self._llm = llm_service or get_llm_service()
        self._logger = logger

    def execute(
        self,
        intent: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> RAGResult:
        """Execute full RAG pipeline (synchronous).

        Args:
            intent: Classified intent.
            user_message: Current user query.
            history: Conversation history.

        Returns:
            RAGResult with generated text and metadata.
        """
        retrieval_start = time.perf_counter()
        documents = self._retriever.retrieve(user_message)
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

        messages = RAGPromptBuilder.build(
            intent=intent,
            user_message=user_message,
            documents=documents,
            history=history,
        )

        gen_start = time.perf_counter()
        try:
            result = self._llm.generate_chat(messages)
            gen_ms = (time.perf_counter() - gen_start) * 1000

            self._record_llm_metrics(result.get("usage", {}), gen_ms / 1000)
            LLM_REQUESTS_TOTAL.labels(status="success").inc()

            return RAGResult(
                text=result["text"],
                intent=intent,
                documents=documents,
                usage=result.get("usage", {}),
                retrieval_time_ms=retrieval_ms,
                generation_time_ms=gen_ms,
            )
        except Exception:
            LLM_REQUESTS_TOTAL.labels(status="error").inc()
            raise

    def execute_stream(
        self,
        intent: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[Iterator[str], list[RetrievedDocument]]:
        """Execute RAG pipeline with streaming LLM output.

        The retrieval step is synchronous; only LLM generation streams.

        Args:
            intent: Classified intent.
            user_message: Current user query.
            history: Conversation history.

        Returns:
            Tuple of (token iterator, retrieved documents).
        """
        documents = self._retriever.retrieve(user_message)

        messages = RAGPromptBuilder.build(
            intent=intent,
            user_message=user_message,
            documents=documents,
            history=history,
        )

        token_stream = self._llm.generate_stream(messages)
        return token_stream, documents

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
