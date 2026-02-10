"""Intent router dispatching queries to appropriate pipelines.

Routes classified intents to: template responses, RAG+LLM pipeline,
LLM-only pipeline, or database queries.
"""

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.database.models.tmdb import Film
from src.database.repositories.tmdb.film import FilmRepository
from src.etl.utils.logger import setup_logger
from src.monitoring.metrics import (
    CLASSIFIER_CONFIDENCE,
    CLASSIFIER_REQUEST_DURATION,
    CLASSIFIER_REQUESTS_TOTAL,
)
from src.services.chat.session import SessionManager, get_session_manager
from src.services.intent.classifier import IntentClassifier, get_intent_classifier
from src.services.intent.prompts import get_template_response
from src.services.llm.llm_service import LLMService, get_llm_service

if TYPE_CHECKING:
    from src.services.rag.pipeline import RAGPipeline

logger = setup_logger("services.intent.router")

# =============================================================================
# INTENT ROUTING CONSTANTS
# =============================================================================

RAG_INTENTS = {"horror_recommendation", "horror_trivia"}
LLM_ONLY_INTENTS = {"horror_discussion"}
TEMPLATE_INTENTS = {"greeting", "farewell", "out_of_scope"}
DB_QUERY_INTENTS = {"film_details"}

# Common question prefixes to strip when extracting film title
_FILM_QUERY_PREFIXES = [
    "tell me about",
    "parle-moi de",
    "parle moi de",
    "dis-moi",
    "dis moi",
    "quelle est la note de",
    "quelle est la note du film",
    "what is",
    "what's",
    "info on",
    "details about",
    "details sur",
    "details for",
    "information about",
    "information on",
    "information sur",
    "look up",
    "find",
    "search for",
    "search",
    "show me",
    "montre-moi",
    "cherche",
]

_FILM_QUERY_SUFFIXES = [
    "the movie",
    "the film",
    "le film",
    "movie",
    "film",
]


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

    Attributes:
        _classifier: Intent classifier service.
        _rag_pipeline: RAG pipeline for retrieval+generation.
        _llm: LLM service for direct generation.
        _session_manager: Chat session manager.
    """

    def __init__(
        self,
        classifier: IntentClassifier | None = None,
        rag_pipeline: "RAGPipeline | None" = None,
        llm_service: LLMService | None = None,
        session_manager: SessionManager | None = None,
    ) -> None:
        """Initialize router with injectable dependencies.

        Args:
            classifier: Override intent classifier (for testing).
            rag_pipeline: Override RAG pipeline (for testing).
            llm_service: Override LLM service (for testing).
            session_manager: Override session manager (for testing).
        """
        self._classifier = classifier or get_intent_classifier()
        if rag_pipeline is None:
            from src.services.rag.pipeline import RAGPipeline

            self._rag_pipeline = RAGPipeline()
        else:
            self._rag_pipeline = rag_pipeline
        self._llm = llm_service or get_llm_service()
        self._session_manager = session_manager or get_session_manager()
        self._logger = logger

    def handle(
        self,
        user_message: str,
        session_id: UUID | None,
        user_id: str,
        db_session: Session | None = None,
    ) -> ChatResult:
        """Handle a user message (synchronous response).

        Args:
            user_message: The user's query text.
            session_id: Existing session ID, or None for new.
            user_id: Authenticated user identifier.
            db_session: SQLAlchemy session for film_details queries.

        Returns:
            ChatResult with text and metadata.
        """
        classification = self._classify_with_metrics(user_message)
        intent = classification["intent"]
        confidence = classification["confidence"]

        session = self._session_manager.get_or_create(session_id, user_id)
        history = self._session_manager.get_history_as_messages(session.session_id)

        if intent in TEMPLATE_INTENTS:
            text = get_template_response(intent) or ""
        elif intent in DB_QUERY_INTENTS:
            text = self._handle_film_details(user_message, db_session)
        elif intent in RAG_INTENTS:
            rag_result = self._rag_pipeline.execute(intent, user_message, history)
            text = rag_result.text
        elif intent in LLM_ONLY_INTENTS:
            text = self._handle_llm_only(intent, user_message, history)
        else:
            text = get_template_response("out_of_scope") or ""

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
        db_session: Session | None = None,
    ) -> tuple[Iterator[str] | None, str, float, UUID, str | None]:
        """Handle a user message with streaming response.

        For non-streamable intents (template, film_details), returns
        the full text directly (iterator is None).

        Args:
            user_message: The user's query text.
            session_id: Existing session ID, or None for new.
            user_id: Authenticated user identifier.
            db_session: SQLAlchemy session for film_details queries.

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
            text = get_template_response(intent) or ""
            self._session_manager.add_message(session.session_id, "assistant", text)
            return None, intent, confidence, session.session_id, text

        if intent in DB_QUERY_INTENTS:
            text = self._handle_film_details(user_message, db_session)
            self._session_manager.add_message(session.session_id, "assistant", text)
            return None, intent, confidence, session.session_id, text

        if intent in RAG_INTENTS:
            token_stream, _docs = self._rag_pipeline.execute_stream(
                intent,
                user_message,
                history,
            )
            return token_stream, intent, confidence, session.session_id, None

        if intent in LLM_ONLY_INTENTS:
            from src.services.rag.prompt_builder import RAGPromptBuilder

            messages = RAGPromptBuilder.build(
                intent=intent,
                user_message=user_message,
                documents=None,
                history=history,
            )
            token_stream = self._llm.generate_stream(messages)
            return token_stream, intent, confidence, session.session_id, None

        # Fallback
        text = get_template_response("out_of_scope") or ""
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

    def _handle_llm_only(
        self,
        intent: str,
        user_message: str,
        history: list[dict[str, str]],
    ) -> str:
        """Handle intents that use LLM without RAG retrieval.

        Args:
            intent: Classified intent.
            user_message: User query.
            history: Conversation history.

        Returns:
            Generated response text.
        """
        from src.services.rag.prompt_builder import RAGPromptBuilder

        messages = RAGPromptBuilder.build(
            intent=intent,
            user_message=user_message,
            documents=None,
            history=history,
        )
        result = self._llm.generate_chat(messages)
        return result["text"]

    def _handle_film_details(
        self,
        user_message: str,
        db_session: Session | None,
    ) -> str:
        """Handle film_details intent by querying the films database.

        Args:
            user_message: User query containing a film reference.
            db_session: SQLAlchemy session for the main database.

        Returns:
            Formatted film details text, or error message.
        """
        if db_session is None:
            return (
                "Je voudrais bien chercher ce film pour vous, mais la base de "
                "donnees n'est pas accessible pour le moment. Reessayez plus tard."
            )

        query = self._extract_film_query(user_message)
        repo = FilmRepository(db_session)
        films = repo.search_by_title(query, limit=3)

        if not films:
            return (
                f"Je n'ai pas trouve de film correspondant a '{query}' dans notre base. "
                "Essayez avec le titre exact, ou demandez-moi une recommandation !"
            )

        return self._format_film_details(films[0])

    @staticmethod
    def _extract_film_query(message: str) -> str:
        """Extract likely film name from user message.

        Simple heuristic: remove common question prefixes/suffixes.

        Args:
            message: Raw user message.

        Returns:
            Cleaned query string for title search.
        """
        lower = message.lower().strip()

        for prefix in _FILM_QUERY_PREFIXES:
            if lower.startswith(prefix):
                lower = lower[len(prefix) :].strip()
                break

        lower = lower.rstrip("?!. ")

        for suffix in _FILM_QUERY_SUFFIXES:
            if lower.endswith(suffix):
                lower = lower[: -len(suffix)].strip()

        return lower if lower else message

    @staticmethod
    def _format_film_details(film: Film) -> str:
        """Format a Film model into a human-readable response.

        Args:
            film: Film ORM model instance.

        Returns:
            Formatted film details string.
        """
        lines = [f"**{film.title}**"]

        if film.release_date:
            lines.append(f"Sortie : {film.release_date.strftime('%d/%m/%Y')}")
        if film.vote_average:
            lines.append(f"Note TMDB : {film.vote_average}/10")
        if film.vote_count:
            lines.append(f"Votes : {film.vote_count:,}")
        if film.runtime:
            hours = film.runtime // 60
            minutes = film.runtime % 60
            lines.append(f"Duree : {hours}h{minutes:02d}")
        if film.overview:
            lines.append(f"\n{film.overview}")
        if film.tagline:
            lines.append(f'\n_"{film.tagline}"_')

        return "\n".join(lines)


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
