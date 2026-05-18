"""Tests for strict RAG system prompt constraints.

Validates that SYSTEM_PROMPT_RAG enforces no hallucination, strict context adherence,
and bilingual title support.
"""

import pytest

from src.services.intent.prompts import SYSTEM_PROMPT_RAG, get_system_prompt


class TestRagPromptStrict:
    """Validation suite for strict RAG system prompt."""

    def test_rag_prompt_contains_strict_rules(self) -> None:
        """Verify SYSTEM_PROMPT_RAG includes key constraint keywords.

        These keywords signal absolute rules against hallucination and
        context fabrication.
        """
        required_keywords = {
            "UNIQUEMENT",
            "JAMAIS",
            "information fiable",
        }
        for keyword in required_keywords:
            assert keyword in SYSTEM_PROMPT_RAG, (
                f"Missing constraint keyword '{keyword}' in SYSTEM_PROMPT_RAG. "
                "Ensure hallucination rules are explicit."
            )

    def test_rag_prompt_has_french_language_instruction(self) -> None:
        """Verify prompt explicitly requires French output."""
        assert "Réponds en français" in SYSTEM_PROMPT_RAG, (
            "Missing explicit French language instruction in SYSTEM_PROMPT_RAG. "
            "Output language must be declared."
        )

    def test_rag_prompt_preserves_context_placeholder(self) -> None:
        """Verify {context} placeholder is present for RAG injection."""
        assert "{context}" in SYSTEM_PROMPT_RAG, (
            "Missing {context} placeholder in SYSTEM_PROMPT_RAG. "
            "Context cannot be injected without this placeholder."
        )

    def test_system_prompt_needs_database_uses_rag_prompt(self) -> None:
        """Verify get_system_prompt('needs_database') returns SYSTEM_PROMPT_RAG."""
        prompt = get_system_prompt("needs_database")
        assert prompt == SYSTEM_PROMPT_RAG, (
            "System prompt for 'needs_database' intent should use SYSTEM_PROMPT_RAG. "
            "This ensures consistent strict hallucination prevention."
        )

    def test_rag_prompt_forbids_invented_actors(self) -> None:
        """Verify prompt explicitly forbids actor/director invention."""
        assert "noms d'acteurs, réalisateurs" in SYSTEM_PROMPT_RAG, (
            "Prompt must explicitly forbid inventing actor/director names. "
            "This prevents hallucinations like 'Jennifer Kent' for Babadook."
        )

    def test_rag_prompt_bilingual_title_support(self) -> None:
        """Verify prompt acknowledges French/English title equivalence."""
        assert "français ou en anglais" in SYSTEM_PROMPT_RAG, (
            "Prompt must clarify that titles are valid in both FR and EN. "
            "Sources expose both title and title_fr."
        )

    def test_rag_prompt_context_fallback(self) -> None:
        """Verify explicit fallback message when context is insufficient."""
        assert "Je n'ai pas trouvé d'information fiable" in SYSTEM_PROMPT_RAG, (
            "Prompt must include explicit no-hallucination fallback message. "
            "This prevents LLM from inventing answers when context is empty."
        )
