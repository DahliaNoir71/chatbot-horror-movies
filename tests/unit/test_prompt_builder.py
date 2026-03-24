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
    def test_basic_structure_system_context_user():
        """Minimal call produces [system, context, user] messages."""
        messages = RAGPromptBuilder.build(
            intent="needs_database",
            user_message="Pourquoi l'horreur ?",
        )

        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "system"  # context block (empty)
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Pourquoi l'horreur ?"

    @staticmethod
    def test_with_documents_adds_context_block(sample_documents):
        """When documents are provided, context block contains document data."""
        messages = RAGPromptBuilder.build(
            intent="needs_database",
            user_message="Recommande un film",
            documents=sample_documents,
        )

        # system + context + user = 3 messages
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "system"  # context block
        assert "The Conjuring" in messages[1]["content"]
        assert messages[-1]["role"] == "user"

    @staticmethod
    def test_without_documents_explicit_empty_context():
        """Without documents, an explicit empty context block is added."""
        messages = RAGPromptBuilder.build(
            intent="needs_database",
            user_message="Discussion",
            documents=None,
        )

        # system + empty context + user = 3
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "system"
        assert "Aucun document pertinent" in messages[1]["content"]
        assert messages[2]["role"] == "user"

    @staticmethod
    def test_empty_documents_explicit_empty_context():
        """Empty document list produces explicit empty context block."""
        messages = RAGPromptBuilder.build(
            intent="needs_database",
            user_message="Discussion",
            documents=[],
        )

        assert len(messages) == 3
        assert "Aucun document pertinent" in messages[1]["content"]

    @staticmethod
    def test_with_history_inserts_before_user():
        """Conversation history is placed between context and user."""
        history = [
            {"role": "user", "content": "Bonjour"},
            {"role": "assistant", "content": "Bienvenue !"},
        ]

        messages = RAGPromptBuilder.build(
            intent="needs_database",
            user_message="Nouvelle question",
            history=history,
        )

        # system + context + 2 history + user = 5
        assert len(messages) == 5
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "system"  # context
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "Bonjour"
        assert messages[3]["role"] == "assistant"
        assert messages[4]["role"] == "user"
        assert messages[4]["content"] == "Nouvelle question"

    @staticmethod
    def test_empty_history_ignored():
        """Empty history list does not add extra messages."""
        messages = RAGPromptBuilder.build(
            intent="needs_database",
            user_message="Question",
            history=[],
        )

        # system + context + user = 3
        assert len(messages) == 3

    @staticmethod
    def test_system_prompt_matches_intent():
        """System prompt content matches the intent-specific prompt."""
        messages = RAGPromptBuilder.build(intent="needs_database", user_message="test")
        expected_prompt = get_system_prompt("needs_database")
        assert messages[0]["content"] == expected_prompt

    @staticmethod
    def test_single_system_prompt_used(sample_documents):
        """Same system prompt is used regardless of documents presence."""
        messages_no_docs = RAGPromptBuilder.build(
            intent="needs_database",
            user_message="test",
        )
        messages_with_docs = RAGPromptBuilder.build(
            intent="needs_database",
            user_message="test",
            documents=sample_documents,
        )

        assert messages_no_docs[0]["content"] == messages_with_docs[0]["content"]

    @staticmethod
    def test_full_message_order_with_all_components(sample_documents):
        """Full call with documents + history has correct order."""
        history = [{"role": "user", "content": "prev"}]

        messages = RAGPromptBuilder.build(
            intent="needs_database",
            user_message="current",
            documents=sample_documents,
            history=history,
        )

        # system, context, history(1), user
        assert len(messages) == 4
        roles = [m["role"] for m in messages]
        assert roles == ["system", "system", "user", "user"]
        assert messages[-1]["content"] == "current"

    @staticmethod
    def test_history_truncated_to_max():
        """History is truncated to the last 6 messages (3 turns)."""
        history = [
            {"role": "user", "content": f"msg{i}"}
            for i in range(10)
        ]

        messages = RAGPromptBuilder.build(
            intent="needs_database",
            user_message="current",
            history=history,
        )

        # system + context + 6 history + user = 9
        assert len(messages) == 9
        # First history message should be msg4 (10 - 6 = 4)
        assert messages[2]["content"] == "msg4"


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
    def test_header_line():
        """Context block starts with the strict context header."""
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

        assert context.startswith("=== CONTEXTE DOCUMENTAIRE (source de verite) ===")

    @staticmethod
    def test_empty_documents_explicit_message():
        """Empty documents produce an explicit 'no documents found' message."""
        context = RAGPromptBuilder._format_context(None)

        assert "Aucun document pertinent" in context
        assert "CONTEXTE DOCUMENTAIRE" in context
