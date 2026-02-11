"""T9 — Response quality tests (manual evaluation v1).

Validates response structure, prompt construction quality, and keyword
presence without requiring deepeval/ragas. Uses fixtures and the real
prompt builder to verify the pipeline produces coherent outputs.

Approach v1: structural validation + keyword matching on mock responses.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.services.intent.prompts import (
    SYSTEM_PROMPTS,
    TEMPLATE_RESPONSES,
    get_system_prompt,
    get_template_response,
)
from src.services.rag.prompt_builder import RAGPromptBuilder
from src.services.rag.retriever import RetrievedDocument


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_rag_documents() -> list[RetrievedDocument]:
    """Sample documents for prompt quality tests."""
    return [
        RetrievedDocument(
            id=uuid4(),
            content="The Conjuring (2013) directed by James Wan is a supernatural horror classic.",
            source_type="film_overview",
            source_id=185,
            metadata={"title": "The Conjuring", "year": 2013, "vote_average": 7.5},
            similarity=0.85,
        ),
        RetrievedDocument(
            id=uuid4(),
            content="Hereditary (2018) by Ari Aster explores grief through supernatural horror.",
            source_type="film_overview",
            source_id=438631,
            metadata={"title": "Hereditary", "year": 2018, "vote_average": 8.3},
            similarity=0.78,
        ),
    ]


# =========================================================================
# T9 — Response structure validation (template responses)
# =========================================================================


@pytest.mark.model
class TestResponseStructure:
    """T9 — Validate structure and content of template responses."""

    @staticmethod
    def test_greeting_response_is_in_french():
        """Greeting template response is in French."""
        text = get_template_response("greeting")
        assert text is not None
        assert "Bonjour" in text or "bonjour" in text

    @staticmethod
    def test_greeting_mentions_capabilities():
        """Greeting response describes what HorrorBot can do."""
        text = get_template_response("greeting")
        assert "recommander" in text.lower() or "films" in text.lower()

    @staticmethod
    def test_farewell_is_polite():
        """Farewell template is polite and mentions horror."""
        text = get_template_response("farewell")
        assert text is not None
        assert "revoir" in text.lower() or "merci" in text.lower()

    @staticmethod
    def test_out_of_scope_redirects():
        """Out-of-scope template redirects to horror topics."""
        text = get_template_response("out_of_scope")
        assert text is not None
        assert "horreur" in text.lower() or "horror" in text.lower()

    @staticmethod
    def test_all_template_responses_non_empty():
        """All template responses are non-empty strings."""
        for intent in ["greeting", "farewell", "out_of_scope"]:
            text = get_template_response(intent)
            assert text is not None
            assert len(text.strip()) > 20, f"Template for '{intent}' is too short"

    @staticmethod
    def test_mock_recommendation_contains_film_title(mock_llm_responses):
        """Mock recommendation response mentions a film title."""
        text = mock_llm_responses["horror_recommendation"]["text"]
        # Should reference at least one known horror film
        assert any(
            title in text
            for title in ["Conjuring", "Hereditary", "Shining", "Exorcist"]
        ), f"No film title found in: {text}"

    @staticmethod
    def test_mock_recommendation_contains_year(mock_llm_responses):
        """Mock recommendation mentions a year."""
        text = mock_llm_responses["horror_recommendation"]["text"]
        import re

        years = re.findall(r"\b(19|20)\d{2}\b", text)
        assert len(years) > 0, f"No year found in recommendation: {text}"

    @staticmethod
    def test_mock_trivia_contains_factual_info(mock_llm_responses):
        """Mock trivia response contains factual keywords."""
        text = mock_llm_responses["horror_trivia"]["text"]
        assert any(
            kw in text.lower()
            for kw in ["réalisé", "directed", "1973", "friedkin", "william"]
        ), f"No factual info in trivia: {text}"

    @staticmethod
    def test_mock_discussion_is_substantive(mock_llm_responses):
        """Mock discussion response is substantive (> 50 chars)."""
        text = mock_llm_responses["horror_discussion"]["text"]
        assert len(text) > 50, f"Discussion too short ({len(text)} chars): {text}"


# =========================================================================
# T9 — Prompt construction quality
# =========================================================================


@pytest.mark.model
class TestPromptQuality:
    """T9 — Validate that prompts built for the LLM are well-structured."""

    @staticmethod
    def test_rag_prompt_includes_context_documents(sample_rag_documents):
        """RAG prompt includes retrieved document content."""
        messages = RAGPromptBuilder.build(
            intent="horror_recommendation",
            user_message="Recommande un film",
            documents=sample_rag_documents,
        )

        context_block = messages[1]["content"]
        assert "The Conjuring" in context_block
        assert "Hereditary" in context_block

    @staticmethod
    def test_rag_prompt_system_is_intent_specific():
        """System prompt varies by intent."""
        rec_messages = RAGPromptBuilder.build(
            intent="horror_recommendation", user_message="test"
        )
        disc_messages = RAGPromptBuilder.build(
            intent="horror_discussion", user_message="test"
        )

        assert rec_messages[0]["content"] != disc_messages[0]["content"]

    @staticmethod
    def test_recommendation_prompt_mentions_recommendation():
        """Recommendation system prompt mentions recommendation role."""
        prompt = get_system_prompt("horror_recommendation", has_context=True)
        assert "recommand" in prompt.lower() or "suggest" in prompt.lower()

    @staticmethod
    def test_trivia_prompt_mentions_facts():
        """Trivia system prompt mentions factual precision."""
        prompt = get_system_prompt("horror_trivia", has_context=True)
        assert "précis" in prompt.lower() or "expert" in prompt.lower()

    @staticmethod
    def test_history_preserved_in_prompt():
        """Conversation history appears in the built prompt."""
        history = [
            {"role": "user", "content": "J'aime les films de zombies"},
            {"role": "assistant", "content": "Les zombies sont un classique !"},
        ]

        messages = RAGPromptBuilder.build(
            intent="horror_discussion",
            user_message="Autre question",
            history=history,
        )

        all_content = " ".join(m["content"] for m in messages)
        assert "zombies" in all_content
        assert "classique" in all_content

    @staticmethod
    def test_no_context_variant_used_when_empty():
        """When no documents, the no_context system prompt variant is used."""
        messages = RAGPromptBuilder.build(
            intent="horror_recommendation",
            user_message="Recommande un film",
            documents=None,
        )

        system_prompt = messages[0]["content"]
        no_context_prompt = get_system_prompt("horror_recommendation", has_context=False)
        assert system_prompt == no_context_prompt

    @staticmethod
    def test_all_system_prompts_in_french():
        """All system prompts are in French."""
        for key, prompt in SYSTEM_PROMPTS.items():
            assert any(
                word in prompt.lower()
                for word in ["tu es", "reponds", "français", "francais", "horreur"]
            ), f"System prompt '{key}' may not be in French: {prompt[:80]}"


# =========================================================================
# T9 — Keyword validation on quality questions (fixture-driven)
# =========================================================================


@pytest.mark.model
class TestResponseKeywords:
    """T9 — Validate expected keywords in mock responses."""

    @staticmethod
    def test_mock_responses_cover_expected_keywords(mock_llm_responses):
        """Each mock LLM response contains at least one of its domain keywords."""
        domain_keywords = {
            "horror_recommendation": ["film", "horreur", "horror", "recommand"],
            "horror_discussion": ["horreur", "horror", "cinéma", "film"],
            "horror_trivia": ["film", "réalisé", "année", "directed"],
        }

        for intent, keywords in domain_keywords.items():
            if intent not in mock_llm_responses:
                continue
            text = mock_llm_responses[intent]["text"].lower()
            found = [kw for kw in keywords if kw.lower() in text]
            assert len(found) > 0, (
                f"Intent '{intent}' response contains none of {keywords}: {text}"
            )

    @staticmethod
    def test_quality_questions_have_viable_keywords(rag_test_data):
        """Each quality question has at least 2 expected keywords."""
        for q in rag_test_data["quality_questions"]:
            assert len(q["expected_keywords"]) >= 2, (
                f"Query '{q['query']}' has too few keywords: {q['expected_keywords']}"
            )

    @staticmethod
    def test_quality_questions_intents_are_valid(rag_test_data):
        """Quality question intents are valid INTENT_LABELS."""
        from src.services.intent.classifier import INTENT_LABELS

        valid = set(INTENT_LABELS)
        for q in rag_test_data["quality_questions"]:
            assert q["intent"] in valid, (
                f"Invalid intent '{q['intent']}' in quality question: {q['query']}"
            )
