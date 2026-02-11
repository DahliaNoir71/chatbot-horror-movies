"""T2 — Unit tests for IntentRouter dispatch logic.

Tests that each intent is routed to the correct pipeline
(template, RAG, LLM-only, DB query) with fully mocked dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.services.intent.router import (
    DB_QUERY_INTENTS,
    LLM_ONLY_INTENTS,
    RAG_INTENTS,
    TEMPLATE_INTENTS,
    IntentRouter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_classifier(intent: str, confidence: float = 0.90):
    """Return a mock classifier returning the given intent."""
    mock = MagicMock()
    mock.classify.return_value = {
        "intent": intent,
        "confidence": confidence,
        "all_scores": {intent: confidence},
    }
    return mock


def _build_router(
    classifier,
    mock_rag_pipeline,
    mock_llm_service,
    mock_session_manager,
) -> IntentRouter:
    """Build an IntentRouter with all dependencies mocked."""
    return IntentRouter(
        classifier=classifier,
        rag_pipeline=mock_rag_pipeline,
        llm_service=mock_llm_service,
        session_manager=mock_session_manager,
    )


# =========================================================================
# T2 — Dispatch handle() vers le bon pipeline
# =========================================================================


class TestIntentRouterDispatch:
    """T2 — Verify handle() routes each intent to the correct pipeline."""

    @staticmethod
    def test_handle_greeting_returns_template(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """greeting intent returns a template response (no LLM call)."""
        classifier = _make_classifier("greeting")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        result = router.handle("Bonjour", session_id=None, user_id="user1")

        assert result.intent == "greeting"
        assert len(result.text) > 0
        mock_rag_pipeline.execute.assert_not_called()
        mock_llm_service.generate_chat.assert_not_called()

    @staticmethod
    def test_handle_farewell_returns_template(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """farewell intent returns a template response."""
        classifier = _make_classifier("farewell")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        result = router.handle("Au revoir", session_id=None, user_id="user1")

        assert result.intent == "farewell"
        assert len(result.text) > 0
        mock_rag_pipeline.execute.assert_not_called()

    @staticmethod
    def test_handle_out_of_scope_returns_template(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """out_of_scope intent returns a redirection template."""
        classifier = _make_classifier("out_of_scope")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        result = router.handle("Quelle est la capitale ?", session_id=None, user_id="user1")

        assert result.intent == "out_of_scope"
        assert len(result.text) > 0

    @staticmethod
    def test_handle_horror_recommendation_calls_rag(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """horror_recommendation intent triggers RAG pipeline."""
        classifier = _make_classifier("horror_recommendation")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        result = router.handle("Recommande un film", session_id=None, user_id="user1")

        assert result.intent == "horror_recommendation"
        mock_rag_pipeline.execute.assert_called_once()

    @staticmethod
    def test_handle_horror_trivia_calls_rag(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """horror_trivia intent triggers RAG pipeline."""
        classifier = _make_classifier("horror_trivia")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        result = router.handle("Qui a réalisé L'Exorciste ?", session_id=None, user_id="user1")

        assert result.intent == "horror_trivia"
        mock_rag_pipeline.execute.assert_called_once()

    @staticmethod
    def test_handle_horror_discussion_calls_llm_only(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """horror_discussion intent calls LLM directly (no RAG retrieval)."""
        classifier = _make_classifier("horror_discussion")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        result = router.handle("Pourquoi le found footage ?", session_id=None, user_id="user1")

        assert result.intent == "horror_discussion"
        mock_llm_service.generate_chat.assert_called_once()
        mock_rag_pipeline.execute.assert_not_called()

    @staticmethod
    def test_handle_film_details_queries_db(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """film_details intent queries the database (no LLM, no RAG)."""
        classifier = _make_classifier("film_details")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        # No db_session → should return a graceful error message
        result = router.handle("Quelle est la note de The Shining ?", session_id=None, user_id="user1")

        assert result.intent == "film_details"
        mock_rag_pipeline.execute.assert_not_called()
        mock_llm_service.generate_chat.assert_not_called()
        assert "base de donnees" in result.text.lower() or len(result.text) > 0


# =========================================================================
# T2 — Dispatch handle_stream()
# =========================================================================


class TestIntentRouterStream:
    """T2 — Verify handle_stream() routes correctly."""

    @staticmethod
    def test_stream_template_returns_direct_text(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """Template intents return direct text (no iterator)."""
        classifier = _make_classifier("greeting")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        iterator, intent, _, _, direct_text = router.handle_stream(
            "Bonjour", session_id=None, user_id="user1"
        )

        assert iterator is None
        assert direct_text is not None
        assert intent == "greeting"

    @staticmethod
    def test_stream_rag_returns_iterator(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """RAG intents return a token iterator."""
        classifier = _make_classifier("horror_recommendation")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        iterator, intent, _, _, direct_text = router.handle_stream(
            "Recommande un film", session_id=None, user_id="user1"
        )

        assert iterator is not None
        assert direct_text is None
        assert intent == "horror_recommendation"

    @staticmethod
    def test_stream_llm_only_returns_iterator(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """LLM-only intents return a token iterator."""
        classifier = _make_classifier("horror_discussion")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        iterator, intent, _, _, direct_text = router.handle_stream(
            "Pourquoi l'horreur ?", session_id=None, user_id="user1"
        )

        assert iterator is not None
        assert direct_text is None
        assert intent == "horror_discussion"


# =========================================================================
# T2 — Fallback behavior
# =========================================================================


class TestIntentRouterFallback:
    """T2 — Fallback and edge-case behavior."""

    @staticmethod
    def test_unknown_intent_returns_out_of_scope(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """An unknown intent falls back to out_of_scope template."""
        classifier = _make_classifier("totally_unknown_intent")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        result = router.handle("random text", session_id=None, user_id="user1")

        assert len(result.text) > 0
        mock_rag_pipeline.execute.assert_not_called()
        mock_llm_service.generate_chat.assert_not_called()

    @staticmethod
    def test_session_messages_stored(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """User and assistant messages are stored in session after handle()."""
        classifier = _make_classifier("greeting")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)

        router.handle("Bonjour", session_id=None, user_id="user1")

        # Should have stored both user and assistant messages
        assert mock_session_manager.add_message.call_count == 2

    @staticmethod
    def test_existing_session_reused(
        mock_rag_pipeline, mock_llm_service, mock_session_manager
    ):
        """An existing session_id is passed to session manager."""
        classifier = _make_classifier("greeting")
        router = _build_router(classifier, mock_rag_pipeline, mock_llm_service, mock_session_manager)
        existing_id = uuid4()

        router.handle("Bonjour", session_id=existing_id, user_id="user1")

        mock_session_manager.get_or_create.assert_called_once_with(existing_id, "user1")


# =========================================================================
# T2 — _extract_film_query helper
# =========================================================================


class TestExtractFilmQuery:
    """T2 — Film title extraction from user queries."""

    @staticmethod
    def test_strips_french_prefix():
        """French question prefixes are removed."""
        assert IntentRouter._extract_film_query("Quelle est la note de The Shining ?") == "the shining"

    @staticmethod
    def test_strips_english_prefix():
        """English prefixes like 'tell me about' are removed."""
        assert IntentRouter._extract_film_query("Tell me about The Conjuring") == "the conjuring"

    @staticmethod
    def test_strips_suffix():
        """Suffixes like 'the movie' or 'le film' are removed."""
        result = IntentRouter._extract_film_query("details about Scream the movie")
        assert "scream" in result
        assert "movie" not in result

    @staticmethod
    def test_preserves_raw_if_no_match():
        """If no prefix/suffix matches, return lowercased input."""
        assert IntentRouter._extract_film_query("Hereditary") == "hereditary"

    @staticmethod
    def test_strips_punctuation():
        """Trailing punctuation is stripped."""
        result = IntentRouter._extract_film_query("Show me The Exorcist!")
        assert result.endswith("exorcist")


# =========================================================================
# T2 — Intent routing constants coverage
# =========================================================================


class TestRoutingConstants:
    """T2 — Verify routing constant sets are disjoint and complete."""

    @staticmethod
    def test_intent_sets_are_disjoint():
        """No intent appears in more than one routing set."""
        all_sets = [RAG_INTENTS, LLM_ONLY_INTENTS, TEMPLATE_INTENTS, DB_QUERY_INTENTS]
        seen = set()
        for intent_set in all_sets:
            assert seen.isdisjoint(intent_set), f"Overlap found: {seen & intent_set}"
            seen.update(intent_set)

    @staticmethod
    def test_all_seven_intents_routed():
        """All 7 defined intents are covered by routing constants."""
        from src.services.intent.classifier import INTENT_LABELS

        routed = RAG_INTENTS | LLM_ONLY_INTENTS | TEMPLATE_INTENTS | DB_QUERY_INTENTS
        for label in INTENT_LABELS:
            assert label in routed, f"Intent '{label}' has no routing rule"
