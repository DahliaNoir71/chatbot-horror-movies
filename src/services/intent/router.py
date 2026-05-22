"""Intent router dispatching queries to appropriate pipelines.

Routes classified intents to: template responses or RAG+LLM pipeline.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.etl.utils.logger import setup_logger
from src.monitoring.metrics import (
    CLASSIFIER_CONFIDENCE,
    CLASSIFIER_REQUEST_DURATION,
    CLASSIFIER_REQUESTS_TOTAL,
)
from src.services.chat.session import SessionManager, get_session_manager
from src.services.intent.classifier import IntentClassifier, get_intent_classifier
from src.services.intent.prompts import get_template_response

if TYPE_CHECKING:
    from src.services.rag.pipeline import RAGPipeline

logger = setup_logger("services.intent.router")

# =============================================================================
# INTENT ROUTING CONSTANTS
# =============================================================================

RAG_INTENTS = {"needs_database"}
TEMPLATE_INTENTS = {"conversational", "thanks", "off_topic"}


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ChatResult:
    """Unified response from intent routing.

    Attributes:
        text: Response text.
        intent: Classified intent.
        confidence: Classifier confidence score.
        session_id: Session UUID.
        usage: Optional LLM usage stats.
        documents: Retrieved documents (RAG intents only).
        classification_ms: Intent classification duration.
        retrieval_ms: Vector retrieval duration.
        rerank_ms: Cross-encoder reranking duration.
        generation_ms: LLM generation duration.
        total_ms: End-to-end duration.
    """

    text: str
    intent: str
    confidence: float
    session_id: UUID
    usage: dict[str, Any] = field(default_factory=dict)
    documents: list = field(default_factory=list)
    classification_ms: float = 0.0
    retrieval_ms: float = 0.0
    rerank_ms: float = 0.0
    generation_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class StreamEvent:
    """A domain-level event emitted while streaming a response.

    Attributes:
        type: Event kind — "stage", "chunk" or "done".
        stage: Pipeline stage name (for type="stage").
        content: Text fragment (for type="chunk").
        intent: Classified intent (for type="done").
        confidence: Classifier confidence (for type="done").
        session_id: Session UUID (for type="done").
        documents: RAG documents used as context (for type="done").
    """

    type: str
    stage: str | None = None
    content: str | None = None
    intent: str | None = None
    confidence: float | None = None
    session_id: UUID | None = None
    documents: list = field(default_factory=list)


# Sentinel returned by next() when the blocking LLM token iterator is
# exhausted — it is advanced one token at a time from a worker thread.
_STREAM_END = object()


# =============================================================================
# INTENT ROUTER
# =============================================================================


class IntentRouter:
    """Routes user queries to the appropriate processing pipeline.

    Orchestrates: classify -> route -> execute -> respond.
    Two routes: template (conversational/off_topic) or RAG (needs_database).

    Attributes:
        _classifier: Intent classifier service.
        _rag_pipeline: RAG pipeline for retrieval+generation.
        _session_manager: Chat session manager.
    """

    def __init__(
        self,
        classifier: IntentClassifier | None = None,
        rag_pipeline: "RAGPipeline | None" = None,
        session_manager: SessionManager | None = None,
    ) -> None:
        """Initialize router with injectable dependencies.

        Args:
            classifier: Override intent classifier (for testing).
            rag_pipeline: Override RAG pipeline (for testing).
            session_manager: Override session manager (for testing).
        """
        self._classifier = classifier or get_intent_classifier()
        if rag_pipeline is None:
            from src.services.rag.pipeline import RAGPipeline

            self._rag_pipeline = RAGPipeline()
        else:
            self._rag_pipeline = rag_pipeline
        self._session_manager = session_manager or get_session_manager()
        self._logger = logger

    async def handle(
        self,
        user_message: str,
        session_id: UUID | None,
        user_id: str,
    ) -> ChatResult:
        """Handle a user message and return a complete response.

        Args:
            user_message: The user's query text.
            session_id: Existing session ID, or None for new.
            user_id: Authenticated user identifier.

        Returns:
            ChatResult with text and metadata.
        """
        total_start = time.perf_counter()

        classification = await self._classify_with_metrics(user_message)
        intent = classification["intent"]
        confidence = classification["confidence"]
        classification_ms = classification["duration_ms"]

        session = self._session_manager.get_or_create(session_id, user_id)
        history = self._session_manager.get_history_as_messages(session.session_id)

        documents = []
        usage = {}
        retrieval_ms = 0.0
        rerank_ms = 0.0
        generation_ms = 0.0

        if intent in TEMPLATE_INTENTS:
            text = get_template_response(intent, user_message) or ""
        elif intent in RAG_INTENTS:
            rag_result = await self._rag_pipeline.execute(intent, user_message, history)
            text = rag_result.text
            documents = rag_result.documents
            usage = rag_result.usage
            retrieval_ms = rag_result.retrieval_time_ms
            rerank_ms = rag_result.rerank_time_ms
            generation_ms = rag_result.generation_time_ms
        else:
            text = get_template_response("off_topic", user_message) or ""

        self._session_manager.add_message(session.session_id, "user", user_message)
        self._session_manager.add_message(session.session_id, "assistant", text)

        total_ms = (time.perf_counter() - total_start) * 1000

        return ChatResult(
            text=text,
            intent=intent,
            confidence=confidence,
            session_id=session.session_id,
            usage=usage,
            documents=documents,
            classification_ms=classification_ms,
            retrieval_ms=retrieval_ms,
            rerank_ms=rerank_ms,
            generation_ms=generation_ms,
            total_ms=total_ms,
        )

    async def handle_stream(
        self,
        user_message: str,
        session_id: UUID | None,
        user_id: str,
    ) -> AsyncIterator[StreamEvent]:
        """Handle a user message, streaming progress and response events.

        A `classification` stage marker is yielded before any slow work,
        so the SSE client sees activity immediately; the method then
        delegates to the template or RAG sub-stream.

        Args:
            user_message: The user's query text.
            session_id: Existing session ID, or None for new.
            user_id: Authenticated user identifier.

        Yields:
            StreamEvent objects: stage markers, text chunks, then done.
        """
        yield StreamEvent(type="stage", stage="classification")

        classification = await self._classify_with_metrics(user_message)
        intent = classification["intent"]
        confidence = classification["confidence"]

        session = self._session_manager.get_or_create(session_id, user_id)
        sid = session.session_id
        history = self._session_manager.get_history_as_messages(sid)
        self._session_manager.add_message(sid, "user", user_message)

        if intent in RAG_INTENTS:
            substream = self._stream_rag(intent, confidence, sid, user_message, history)
        else:
            substream = self._stream_template(intent, confidence, sid, user_message)
        async for event in substream:
            yield event

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    async def _stream_template(
        self,
        intent: str,
        confidence: float,
        session_id: UUID,
        user_message: str,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a template intent as a single chunk followed by done.

        Args:
            intent: Classified intent.
            confidence: Classifier confidence.
            session_id: Session UUID.
            user_message: The user's query (drives greeting/farewell pick).

        Yields:
            One chunk event with the template text, then a done event.
        """
        text = (
            get_template_response(intent, user_message)
            or get_template_response("off_topic", user_message)
            or ""
        )
        self._session_manager.add_message(session_id, "assistant", text)
        yield StreamEvent(type="chunk", content=text)
        yield StreamEvent(type="done", intent=intent, confidence=confidence, session_id=session_id)

    async def _stream_rag(
        self,
        intent: str,
        confidence: float,
        session_id: UUID,
        user_message: str,
        history: list[dict[str, str]],
    ) -> AsyncIterator[StreamEvent]:
        """Stream the RAG pipeline: retrieval marker, generation, done.

        The LLM token iterator is blocking; it is advanced one token at a
        time via `asyncio.to_thread` so the event loop keeps flushing SSE.

        Args:
            intent: Classified intent.
            confidence: Classifier confidence.
            session_id: Session UUID.
            user_message: The user's query text.
            history: Conversation history messages.

        Yields:
            Stage markers, one chunk per token, then a done event.
        """
        yield StreamEvent(type="stage", stage="retrieval")
        token_stream, documents = await self._rag_pipeline.execute_stream(
            intent, user_message, history
        )

        yield StreamEvent(type="stage", stage="generation")
        parts: list[str] = []
        while True:
            token = await asyncio.to_thread(next, token_stream, _STREAM_END)
            if token is _STREAM_END:
                break
            parts.append(token)
            yield StreamEvent(type="chunk", content=token)

        self._session_manager.add_message(session_id, "assistant", "".join(parts))
        yield StreamEvent(
            type="done",
            intent=intent,
            confidence=confidence,
            session_id=session_id,
            documents=documents,
        )

    async def _classify_with_metrics(self, text: str) -> dict:
        """Classify intent (CPU-bound, offloaded to a thread) and record metrics.

        Args:
            text: User query text.

        Returns:
            Classification result dict with intent, confidence, duration_ms.
        """
        start = time.perf_counter()
        result = await asyncio.to_thread(self._classifier.classify, text)
        duration = time.perf_counter() - start
        duration_ms = duration * 1000

        CLASSIFIER_REQUEST_DURATION.observe(duration)
        CLASSIFIER_REQUESTS_TOTAL.labels(intent=result["intent"]).inc()
        CLASSIFIER_CONFIDENCE.observe(result["confidence"])

        self._logger.info(
            f"Intent classified: {result['intent']} "
            f"(confidence: {round(result['confidence'], 3)}, "
            f"duration: {round(duration_ms)}ms)"
        )

        result["duration_ms"] = duration_ms
        return result


# =============================================================================
# SINGLETON
# =============================================================================


@lru_cache(maxsize=1)
def get_intent_router() -> IntentRouter:
    """Get singleton IntentRouter instance.

    Returns:
        Cached IntentRouter instance.
    """
    return IntentRouter()
