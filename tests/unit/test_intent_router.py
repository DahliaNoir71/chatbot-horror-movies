"""T2 — Unit tests for IntentRouter dispatch logic.

Tests that each intent is routed to the correct pipeline
(template or RAG) with fully mocked dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.services.intent.router import (
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
    mock_session_manager,
) -> IntentRouter:
    """Build an IntentRouter with all dependencies mocked."""
    return IntentRouter(
        classifier=classifier,
        rag_pipeline=mock_rag_pipeline,
        session_manager=mock_session_manager,
    )


# =========================================================================
# T2 — Dispatch handle() vers le bon pipeline
# =========================================================================


class TestIntentRouterDispatch:
    """T2 — Verify handle() routes each intent to the correct pipeline."""

    @staticmethod
    def test_handle_conversational_returns_template(
        mock_rag_pipeline, mock_session_manager
    ):
        """conversational intent returns a template response (no RAG call)."""
        classifier = _make_classifier("conversational")
        router = _build_router(classifier, mock_rag_pipeline, mock_session_manager)

        result = router.handle("Bonjour", session_id=None, user_id="user1")

        assert result.intent == "conversational"
        assert len(result.text) > 0
        mock_rag_pipeline.execute.assert_not_called()

    @staticmethod
    def test_handle_off_topic_returns_template(
        mock_rag_pipeline, mock_session_manager
    ):
        """off_topic intent returns a redirection template."""
        classifier = _make_classifier("off_topic")
        router = _build_router(classifier, mock_rag_pipeline, mock_session_manager)

        result = router.handle("Quelle est la capitale ?", session_id=None, user_id="user1")

        assert result.intent == "off_topic"
        assert len(result.text) > 0
        mock_rag_pipeline.execute.assert_not_called()

    @staticmethod
    def test_handle_needs_database_calls_rag(
        mock_rag_pipeline, mock_session_manager
    ):
        """needs_database intent triggers RAG pipeline."""
        classifier = _make_classifier("needs_database")
        router = _build_router(classifier, mock_rag_pipeline, mock_session_manager)

        result = router.handle("Recommande un film", session_id=None, user_id="user1")

        assert result.intent == "needs_database"
        mock_rag_pipeline.execute.assert_called_once()


# =========================================================================
# T2 — Dispatch handle_stream()
# =========================================================================


class TestIntentRouterStream:
    """T2 — Verify handle_stream() routes correctly."""

    @staticmethod
    def test_stream_template_returns_direct_text(
        mock_rag_pipeline, mock_session_manager
    ):
        """Template intents return direct text (no iterator)."""
        classifier = _make_classifier("conversational")
        router = _build_router(classifier, mock_rag_pipeline, mock_session_manager)

        iterator, intent, _, _, direct_text, _ = router.handle_stream(
            "Bonjour", session_id=None, user_id="user1"
        )

        assert iterator is None
        assert direct_text is not None
        assert intent == "conversational"

    @staticmethod
    def test_stream_rag_returns_iterator(
        mock_rag_pipeline, mock_session_manager
    ):
        """RAG intents return a token iterator."""
        classifier = _make_classifier("needs_database")
        router = _build_router(classifier, mock_rag_pipeline, mock_session_manager)

        iterator, intent, _, _, direct_text, _ = router.handle_stream(
            "Recommande un film", session_id=None, user_id="user1"
        )

        assert iterator is not None
        assert direct_text is None
        assert intent == "needs_database"


# =========================================================================
# T2 — Fallback behavior
# =========================================================================


class TestIntentRouterFallback:
    """T2 — Fallback and edge-case behavior."""

    @staticmethod
    def test_unknown_intent_returns_template(
        mock_rag_pipeline, mock_session_manager
    ):
        """An unknown intent falls back to off_topic template."""
        classifier = _make_classifier("totally_unknown_intent")
        router = _build_router(classifier, mock_rag_pipeline, mock_session_manager)

        result = router.handle("random text", session_id=None, user_id="user1")

        assert len(result.text) > 0
        mock_rag_pipeline.execute.assert_not_called()

    @staticmethod
    def test_session_messages_stored(
        mock_rag_pipeline, mock_session_manager
    ):
        """User and assistant messages are stored in session after handle()."""
        classifier = _make_classifier("conversational")
        router = _build_router(classifier, mock_rag_pipeline, mock_session_manager)

        router.handle("Bonjour", session_id=None, user_id="user1")

        # Should have stored both user and assistant messages
        assert mock_session_manager.add_message.call_count == 2

    @staticmethod
    def test_existing_session_reused(
        mock_rag_pipeline, mock_session_manager
    ):
        """An existing session_id is passed to session manager."""
        classifier = _make_classifier("conversational")
        router = _build_router(classifier, mock_rag_pipeline, mock_session_manager)
        existing_id = uuid4()

        router.handle("Bonjour", session_id=existing_id, user_id="user1")

        mock_session_manager.get_or_create.assert_called_once_with(existing_id, "user1")


# =========================================================================
# T2 — Intent routing constants coverage
# =========================================================================


class TestRoutingConstants:
    """T2 — Verify routing constant sets are disjoint and complete."""

    @staticmethod
    def test_intent_sets_are_disjoint():
        """No intent appears in more than one routing set."""
        all_sets = [RAG_INTENTS, TEMPLATE_INTENTS]
        seen = set()
        for intent_set in all_sets:
            assert seen.isdisjoint(intent_set), f"Overlap found: {seen & intent_set}"
            seen.update(intent_set)

    @staticmethod
    def test_all_three_intents_routed():
        """All 3 defined intents are covered by routing constants."""
        from src.services.intent.classifier import INTENT_LABELS

        routed = RAG_INTENTS | TEMPLATE_INTENTS
        for label in INTENT_LABELS:
            assert label in routed, f"Intent '{label}' has no routing rule"
