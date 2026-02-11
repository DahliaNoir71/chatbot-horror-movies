"""T7 — Data validation tests for AI model data structures and fixtures.

Validates that dataclass schemas (RetrievedDocument, ChatMessage, Session,
RAGResult, ChatResult) accept valid data and that test fixtures are well-formed.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pytest import approx

from src.services.chat.session import ChatMessage, Session
from src.services.intent.classifier import INTENT_LABELS
from src.services.intent.router import ChatResult
from src.services.rag.pipeline import RAGResult
from src.services.rag.retriever import RetrievedDocument


# =========================================================================
# T7 — RetrievedDocument schema validation
# =========================================================================


@pytest.mark.model
class TestRetrievedDocumentSchema:
    """T7 — Validate RetrievedDocument dataclass constraints."""

    @staticmethod
    def test_required_fields_present():
        """All required fields can be set on construction."""
        doc = RetrievedDocument(
            id=uuid4(),
            content="A horror film about ghosts.",
            source_type="film_overview",
            source_id=42,
            metadata={"title": "Test Film"},
            similarity=0.85,
        )
        assert doc.content == "A horror film about ghosts."
        assert doc.source_id == 42

    @staticmethod
    def test_similarity_between_0_and_1():
        """Similarity scores should be in [0.0, 1.0] range."""
        for val in [0.0, 0.5, 1.0]:
            doc = RetrievedDocument(
                id=uuid4(),
                content="test",
                source_type="film_overview",
                source_id=1,
                metadata={},
                similarity=val,
            )
            assert 0.0 <= doc.similarity <= 1.0

    @staticmethod
    def test_source_type_valid_values():
        """Source type should be a recognized value."""
        valid_types = {"film_overview", "critics_consensus"}
        for stype in valid_types:
            doc = RetrievedDocument(
                id=uuid4(),
                content="test",
                source_type=stype,
                source_id=1,
                metadata={},
                similarity=0.9,
            )
            assert doc.source_type in valid_types

    @staticmethod
    def test_metadata_is_dict():
        """Metadata should be a dict (even if empty)."""
        doc = RetrievedDocument(
            id=uuid4(),
            content="test",
            source_type="film_overview",
            source_id=1,
            metadata={},
            similarity=0.9,
        )
        assert isinstance(doc.metadata, dict)

    @staticmethod
    def test_content_non_empty():
        """Content field should contain actual text."""
        doc = RetrievedDocument(
            id=uuid4(),
            content="This is a valid content string.",
            source_type="film_overview",
            source_id=1,
            metadata={"title": "Test"},
            similarity=0.8,
        )
        assert len(doc.content.strip()) > 0


# =========================================================================
# T7 — Fixture data integrity
# =========================================================================


@pytest.mark.model
class TestFixtureDataIntegrity:
    """T7 — Validate test fixture JSON files are well-formed."""

    @staticmethod
    def test_intent_test_cases_minimum_50_entries(intent_test_cases):
        """intent_test_cases.json contains at least 50 entries."""
        assert len(intent_test_cases) >= 50, (
            f"Only {len(intent_test_cases)} entries, need >= 50"
        )

    @staticmethod
    def test_intent_test_cases_all_intents_covered(intent_test_cases):
        """Every defined intent has at least one test case."""
        covered_intents = {case["expected_intent"] for case in intent_test_cases}
        for label in INTENT_LABELS:
            assert label in covered_intents, f"Intent '{label}' has no test cases"

    @staticmethod
    def test_intent_test_cases_minimum_per_intent(intent_test_cases):
        """Each intent has at least 5 test cases."""
        from collections import Counter

        counts = Counter(case["expected_intent"] for case in intent_test_cases)
        for intent, count in counts.items():
            assert count >= 5, f"Intent '{intent}' only has {count} cases, need >= 5"

    @staticmethod
    def test_intent_test_cases_valid_intent_labels(intent_test_cases):
        """All expected_intent values are valid INTENT_LABELS."""
        valid = set(INTENT_LABELS)
        for case in intent_test_cases:
            assert case["expected_intent"] in valid, (
                f"Invalid intent '{case['expected_intent']}' in: {case['query']}"
            )

    @staticmethod
    def test_intent_test_cases_have_required_keys(intent_test_cases):
        """Each test case has query, expected_intent, and language."""
        for i, case in enumerate(intent_test_cases):
            assert "query" in case, f"Case {i} missing 'query'"
            assert "expected_intent" in case, f"Case {i} missing 'expected_intent'"
            assert "language" in case, f"Case {i} missing 'language'"
            assert case["language"] in {"fr", "en"}, f"Case {i} invalid language"

    @staticmethod
    def test_rag_test_queries_has_similarity_pairs(rag_test_data):
        """rag_test_queries.json has similarity_pairs with at least 10 entries."""
        assert "similarity_pairs" in rag_test_data
        assert len(rag_test_data["similarity_pairs"]) >= 10

    @staticmethod
    def test_rag_test_queries_has_dissimilar_pairs(rag_test_data):
        """rag_test_queries.json has dissimilar_pairs with at least 10 entries."""
        assert "dissimilar_pairs" in rag_test_data
        assert len(rag_test_data["dissimilar_pairs"]) >= 10

    @staticmethod
    def test_rag_test_queries_has_quality_questions(rag_test_data):
        """rag_test_queries.json has quality_questions with at least 15 entries."""
        assert "quality_questions" in rag_test_data
        assert len(rag_test_data["quality_questions"]) >= 15

    @staticmethod
    def test_rag_similarity_pairs_have_required_keys(rag_test_data):
        """Each similarity pair has query_a, query_b, and expected threshold."""
        for pair in rag_test_data["similarity_pairs"]:
            assert "query_a" in pair
            assert "query_b" in pair
            assert "expected_min_similarity" in pair

    @staticmethod
    def test_rag_quality_questions_have_required_keys(rag_test_data):
        """Each quality question has query, expected_keywords, and intent."""
        for q in rag_test_data["quality_questions"]:
            assert "query" in q
            assert "expected_keywords" in q
            assert "intent" in q
            assert isinstance(q["expected_keywords"], list)

    @staticmethod
    def test_mock_llm_responses_has_all_intents(mock_llm_responses):
        """mock_llm_responses.json covers the 3 LLM-using intents."""
        required = {"horror_recommendation", "horror_discussion", "horror_trivia"}
        for intent in required:
            assert intent in mock_llm_responses, f"Missing response for '{intent}'"
            assert "text" in mock_llm_responses[intent]
            assert "usage" in mock_llm_responses[intent]


# =========================================================================
# T7 — Chat data structures
# =========================================================================


@pytest.mark.model
class TestChatDataStructures:
    """T7 — Validate ChatMessage, Session, RAGResult, ChatResult schemas."""

    @staticmethod
    def test_chat_message_requires_role_and_content():
        """ChatMessage stores role and content."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp > 0

    @staticmethod
    def test_session_has_uuid_and_user_id():
        """Session stores session_id UUID and user_id."""
        sid = uuid4()
        session = Session(session_id=sid, user_id="testuser")
        assert session.session_id == sid
        assert session.user_id == "testuser"
        assert isinstance(session.messages, list)

    @staticmethod
    def test_session_default_messages_empty():
        """New session has empty message list."""
        session = Session(session_id=uuid4(), user_id="user1")
        assert session.messages == []

    @staticmethod
    def test_rag_result_has_text_and_intent():
        """RAGResult stores text and intent."""
        result = RAGResult(text="response text", intent="horror_recommendation")
        assert result.text == "response text"
        assert result.intent == "horror_recommendation"
        assert isinstance(result.documents, list)
        assert isinstance(result.usage, dict)

    @staticmethod
    def test_chat_result_has_required_fields():
        """ChatResult stores text, intent, confidence, session_id."""
        sid = uuid4()
        result = ChatResult(
            text="Bonjour !",
            intent="greeting",
            confidence=0.95,
            session_id=sid,
        )
        assert result.text == "Bonjour !"
        assert result.intent == "greeting"
        assert result.confidence == approx(0.95)
        assert result.session_id == sid
        assert isinstance(result.usage, dict)
