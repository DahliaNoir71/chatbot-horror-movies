"""Intent router dispatching queries to appropriate pipelines.

Routes classified intents to: template responses or RAG+LLM pipeline.
"""

import time
from collections.abc import Iterator
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
TEMPLATE_INTENTS = {"conversational", "off_topic"}


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
    """

    text: str
    intent: str
    confidence: float
    session_id: UUID
    usage: dict[str, Any] = field(default_factory=dict)


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

    def handle(
        self,
        user_message: str,
        session_id: UUID | None,
        user_id: str,
    ) -> ChatResult:
        """Handle a user message (synchronous response).

        Args:
            user_message: The user's query text.
            session_id: Existing session ID, or None for new.
            user_id: Authenticated user identifier.

        Returns:
            ChatResult with text and metadata.
        """
        classification = self._classify_with_metrics(user_message)
        intent = classification["intent"]
        confidence = classification["confidence"]

        session = self._session_manager.get_or_create(session_id, user_id)
        history = self._session_manager.get_history_as_messages(session.session_id)

        if intent in TEMPLATE_INTENTS:
            text = get_template_response(intent, user_message) or ""
        elif intent in RAG_INTENTS:
            rag_result = self._rag_pipeline.execute(intent, user_message, history)
            text = rag_result.text
        else:
            text = get_template_response("off_topic", user_message) or ""

        self._session_manager.add_message(session.session_id, "user", user_message)
        self._session_manager.add_message(session.session_id, "assistant", text)

        return ChatResult(
            text=text,
            intent=intent,
            confidence=confidence,
            session_id=session.session_id,
        )

    def handle_stream(
        self,
        user_message: str,
        session_id: UUID | None,
        user_id: str,
    ) -> tuple[Iterator[str] | None, str, float, UUID, str | None]:
        """Handle a user message with streaming response.

        For non-streamable intents (template), returns
        the full text directly (iterator is None).

        Args:
            user_message: The user's query text.
            session_id: Existing session ID, or None for new.
            user_id: Authenticated user identifier.

        Returns:
            Tuple of (token_iterator_or_None, intent, confidence,
                      session_id, direct_text_or_None).
        """
        classification = self._classify_with_metrics(user_message)
        intent = classification["intent"]
        confidence = classification["confidence"]

        session = self._session_manager.get_or_create(session_id, user_id)
        history = self._session_manager.get_history_as_messages(session.session_id)

        # Store user message immediately
        self._session_manager.add_message(session.session_id, "user", user_message)

        if intent in TEMPLATE_INTENTS:
            text = get_template_response(intent, user_message) or ""
            self._session_manager.add_message(session.session_id, "assistant", text)
            return None, intent, confidence, session.session_id, text

        if intent in RAG_INTENTS:
            token_stream, _docs = self._rag_pipeline.execute_stream(
                intent,
                user_message,
                history,
            )
            return token_stream, intent, confidence, session.session_id, None

        # Fallback
        text = get_template_response("off_topic", user_message) or ""
        self._session_manager.add_message(session.session_id, "assistant", text)
        return None, intent, confidence, session.session_id, text

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _classify_with_metrics(self, text: str) -> dict:
        """Classify intent and record metrics.

        Args:
            text: User query text.

        Returns:
            Classification result dict.
        """
        start = time.perf_counter()
        result = self._classifier.classify(text)
        duration = time.perf_counter() - start

        CLASSIFIER_REQUEST_DURATION.observe(duration)
        CLASSIFIER_REQUESTS_TOTAL.labels(intent=result["intent"]).inc()
        CLASSIFIER_CONFIDENCE.observe(result["confidence"])

        self._logger.info(
            f"Intent classified: {result['intent']} "
            f"(confidence: {round(result['confidence'], 3)}, "
            f"duration: {round(duration * 1000)}ms)"
        )

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
