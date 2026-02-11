"""T4 — Unit tests for RAGPromptBuilder.

Tests message list construction: system prompt, context block,
conversation history, and user message ordering.
"""

from __future__ import annotations

import pytest

from src.services.intent.prompts import SYSTEM_PROMPTS, get_system_prompt
from src.services.rag.prompt_builder import RAGPromptBuilder


# =========================================================================
# T4 — build() method
# =========================================================================


class TestPromptBuilderBuild:
    """T4 — Construction of the LLM message list."""

    @staticmethod
    def test_basic_structure_system_then_user():
        """Minimal call produces [system, user] messages."""
        messages = RAGPromptBuilder.build(
            intent="horror_discussion",
            user_message="Pourquoi l'horreur ?",
        )

        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Pourquoi l'horreur ?"

    @staticmethod
    def test_with_documents_adds_context_block(sample_documents):
        """When documents are provided, a context block is inserted."""
        messages = RAGPromptBuilder.build(
            intent="horror_recommendation",
            user_message="Recommande un film",
            documents=sample_documents,
        )

        # system + context + user = 3 messages minimum
        assert len(messages) >= 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "system"  # context block
        assert "The Conjuring" in messages[1]["content"]
        assert messages[-1]["role"] == "user"

    @staticmethod
    def test_without_documents_no_context():
        """Without documents, no context block is added."""
        messages = RAGPromptBuilder.build(
            intent="horror_discussion",
            user_message="Discussion",
            documents=None,
        )

        # Only system + user
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    @staticmethod
    def test_empty_documents_no_context():
        """Empty document list behaves like None."""
        messages = RAGPromptBuilder.build(
            intent="horror_discussion",
            user_message="Discussion",
            documents=[],
        )

        assert len(messages) == 2

    @staticmethod
    def test_with_history_inserts_before_user():
        """Conversation history is placed between system and user."""
        history = [
            {"role": "user", "content": "Bonjour"},
            {"role": "assistant", "content": "Bienvenue !"},
        ]

        messages = RAGPromptBuilder.build(
            intent="horror_discussion",
            user_message="Nouvelle question",
            history=history,
        )

        # system + 2 history + user = 4
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Bonjour"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "Nouvelle question"

    @staticmethod
    def test_empty_history_ignored():
        """Empty history list does not add extra messages."""
        messages = RAGPromptBuilder.build(
            intent="horror_discussion",
            user_message="Question",
            history=[],
        )

        assert len(messages) == 2

    @staticmethod
    def test_system_prompt_matches_intent():
        """System prompt content matches the intent-specific prompt."""
        for intent in ["horror_recommendation", "horror_discussion", "horror_trivia"]:
            messages = RAGPromptBuilder.build(intent=intent, user_message="test")
            expected_prompt = get_system_prompt(intent, has_context=False)
            assert messages[0]["content"] == expected_prompt

    @staticmethod
    def test_with_context_uses_context_variant(sample_documents):
        """When documents are present, has_context=True is used for system prompt."""
        messages = RAGPromptBuilder.build(
            intent="horror_recommendation",
            user_message="test",
            documents=sample_documents,
        )

        expected_prompt = get_system_prompt("horror_recommendation", has_context=True)
        assert messages[0]["content"] == expected_prompt

    @staticmethod
    def test_full_message_order_with_all_components(sample_documents):
        """Full call with documents + history has correct order."""
        history = [{"role": "user", "content": "prev"}]

        messages = RAGPromptBuilder.build(
            intent="horror_recommendation",
            user_message="current",
            documents=sample_documents,
            history=history,
        )

        # system, context, history(1), user
        assert len(messages) == 4
        roles = [m["role"] for m in messages]
        assert roles == ["system", "system", "user", "user"]
        assert messages[-1]["content"] == "current"


# =========================================================================
# T4 — _format_context() method
# =========================================================================


class TestPromptBuilderFormatContext:
    """T4 — Context block formatting from retrieved documents."""

    @staticmethod
    def test_formats_title_year_rating(sample_documents):
        """Context includes title, year, and rating from metadata."""
        context = RAGPromptBuilder._format_context(sample_documents)

        assert "The Conjuring" in context
        assert "2013" in context
        assert "7.5" in context

    @staticmethod
    def test_handles_missing_metadata_fields(sample_documents):
        """Documents with missing metadata fields don't cause errors."""
        # Hereditary has no tomatometer in fixture
        context = RAGPromptBuilder._format_context(sample_documents)

        assert "Hereditary" in context
        assert "2018" in context

    @staticmethod
    def test_multiple_documents_numbered(sample_documents):
        """Multiple documents are numbered [1], [2], etc."""
        context = RAGPromptBuilder._format_context(sample_documents)

        assert "[1]" in context
        assert "[2]" in context

    @staticmethod
    def test_includes_source_type(sample_documents):
        """Source type is included in the context block."""
        context = RAGPromptBuilder._format_context(sample_documents)

        assert "film_overview" in context

    @staticmethod
    def test_includes_tomatometer_when_present(sample_documents):
        """Tomatometer is shown when available in metadata."""
        context = RAGPromptBuilder._format_context(sample_documents)

        assert "Tomatometer" in context
        assert "86" in context

    @staticmethod
    def test_header_line_in_french():
        """Context block starts with the French header."""
        from uuid import uuid4

        from src.services.rag.retriever import RetrievedDocument

        docs = [
            RetrievedDocument(
                id=uuid4(),
                content="Test content",
                source_type="film_overview",
                source_id=1,
                metadata={"title": "Test"},
                similarity=0.9,
            )
        ]
        context = RAGPromptBuilder._format_context(docs)

        assert context.startswith("Voici les informations pertinentes")
