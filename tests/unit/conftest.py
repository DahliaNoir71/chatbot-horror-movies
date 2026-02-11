"""Shared fixtures for unit tests.

Provides mocked AI services and helpers for loading test fixtures.
All fixtures avoid loading real ML models — safe for CI without ML deps.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.services.rag.retriever import RetrievedDocument

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixture loader
# ---------------------------------------------------------------------------


def load_fixture(name: str) -> dict | list:
    """Load a JSON fixture file from tests/fixtures/.

    Args:
        name: Filename (e.g. "intent_test_cases.json").

    Returns:
        Parsed JSON content.
    """
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_documents() -> list[RetrievedDocument]:
    """Two sample RetrievedDocument instances for prompt/pipeline tests."""
    return [
        RetrievedDocument(
            id=uuid4(),
            content="The Conjuring (2013) is a supernatural horror film directed by James Wan.",
            source_type="film_overview",
            source_id=185,
            metadata={
                "title": "The Conjuring",
                "year": 2013,
                "vote_average": 7.5,
                "tomatometer": 86,
            },
            similarity=0.85,
        ),
        RetrievedDocument(
            id=uuid4(),
            content="Hereditary (2018) explores themes of grief and family trauma.",
            source_type="film_overview",
            source_id=438631,
            metadata={
                "title": "Hereditary",
                "year": 2018,
                "vote_average": 8.3,
            },
            similarity=0.78,
        ),
    ]


@pytest.fixture
def mock_llm_responses() -> dict:
    """Load mock LLM responses from fixture file."""
    return load_fixture("mock_llm_responses.json")


# ---------------------------------------------------------------------------
# Mock services
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_classifier():
    """Mock IntentClassifier with injectable classify() return values.

    Default: returns 'greeting' with 0.95 confidence.
    Override via ``mock_classifier.classify.return_value = {...}``.
    """
    mock = MagicMock()
    mock.classify.return_value = {
        "intent": "greeting",
        "confidence": 0.95,
        "all_scores": {"greeting": 0.95, "farewell": 0.02, "out_of_scope": 0.03},
    }
    return mock


@pytest.fixture
def mock_rag_pipeline():
    """Mock RAGPipeline with default execute/execute_stream behavior."""
    from src.services.rag.pipeline import RAGResult

    mock = MagicMock()
    mock.execute.return_value = RAGResult(
        text="Je vous recommande The Conjuring (2013).",
        intent="horror_recommendation",
        documents=[],
        usage={"prompt_tokens": 150, "completion_tokens": 40},
        retrieval_time_ms=50.0,
        generation_time_ms=200.0,
    )
    mock.execute_stream.return_value = (
        iter(["Je ", "vous ", "recommande ", "The ", "Conjuring."]),
        [],
    )
    return mock


@pytest.fixture
def mock_llm_service():
    """Mock LLMService with deterministic responses."""
    mock = MagicMock()
    mock.generate_chat.return_value = {
        "text": "Le found footage fonctionne car il crée un sentiment d'authenticité.",
        "usage": {"prompt_tokens": 120, "completion_tokens": 35},
    }
    mock.generate_stream.return_value = iter(["Le ", "found ", "footage ", "fonctionne."])
    return mock


@pytest.fixture
def mock_session_manager():
    """Mock SessionManager with safe defaults."""
    from src.services.chat.session import Session

    session = Session(session_id=uuid4(), user_id="testuser")
    mock = MagicMock()
    mock.get_or_create.return_value = session
    mock.get_history_as_messages.return_value = []
    mock.add_message.return_value = None
    mock.active_count.return_value = 1
    return mock
