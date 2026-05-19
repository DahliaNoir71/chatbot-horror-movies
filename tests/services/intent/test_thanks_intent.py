"""Tests for the thanks sub-intent (classifier detection + router mapping)."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from src.services.intent.classifier import IntentClassifier
from src.services.intent.prompts import TEMPLATE_RESPONSES, TEMPLATE_THANKS
from src.services.intent.router import IntentRouter


# ---------------------------------------------------------------------------
# Test stubs
# ---------------------------------------------------------------------------


@dataclass
class _FakeSession:
    session_id: UUID = field(default_factory=uuid4)


class _FakeSessionManager:
    def get_or_create(self, session_id, user_id):
        return _FakeSession()

    def get_history_as_messages(self, session_id):
        return []

    def add_message(self, session_id, role, text):
        return None


class _FakeThanksClassifier:
    def classify(self, text: str) -> dict:
        return {"intent": "thanks", "confidence": 1.0, "all_scores": {}}


class _FakeRAGPipeline:
    # Async to match the real RAGPipeline interface; thanks intent never
    # reaches the pipeline, so these stubs are only here for protocol shape.
    async def execute(self, intent, text, history):  # noqa: S7503
        return None

    async def execute_stream(self, intent, text, history):  # noqa: S7503
        return None, []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestThanksIntent:
    """Validates thanks sub-intent detection and routing."""

    def test_classifier_returns_thanks(self) -> None:
        """'Merci beaucoup' is classified as thanks via keyword pre-check."""
        classifier = IntentClassifier()
        result = classifier.classify("Merci beaucoup")
        assert result["intent"] == "thanks"

    def test_classifier_returns_thanks_variant(self) -> None:
        """'Super, merci !' is classified as thanks via keyword pre-check."""
        classifier = IntentClassifier()
        result = classifier.classify("Super, merci !")
        assert result["intent"] == "thanks"

    def test_classifier_returns_thanks_long(self) -> None:
        """Longer gratitude phrase (8 words) is still caught by pre-check."""
        classifier = IntentClassifier()
        result = classifier.classify("Merci pour toute ton aide sur ce sujet")
        assert result["intent"] == "thanks"

    async def test_router_maps_thanks_to_template(self) -> None:
        """Intent 'thanks' is routed to TEMPLATE_THANKS, not TEMPLATE_FAREWELL."""
        router = IntentRouter(
            classifier=_FakeThanksClassifier(),
            rag_pipeline=_FakeRAGPipeline(),
            session_manager=_FakeSessionManager(),
        )
        result = await router.handle("Merci beaucoup", None, "test_user")
        assert result.text == TEMPLATE_THANKS

    async def test_router_distinguishes_thanks_from_farewell(self) -> None:
        """'Merci et au revoir' returns a non-default template response."""
        router = IntentRouter(
            classifier=IntentClassifier(),
            rag_pipeline=_FakeRAGPipeline(),
            session_manager=_FakeSessionManager(),
        )
        result = await router.handle("Merci et au revoir", None, "test_user")
        off_topic = TEMPLATE_RESPONSES.get("off_topic", "")
        assert result.text != off_topic
        assert result.text == TEMPLATE_THANKS
