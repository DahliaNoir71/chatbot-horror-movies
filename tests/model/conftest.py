"""Shared fixtures for model tests.

Loads real ML models and test fixture data.
These tests require the ``ml`` dependency group to be installed.
Run with: ``uv run --group ml pytest tests/model/ -m model -v``
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixture data loaders (module-scoped to avoid repeated I/O)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def intent_test_cases() -> list[dict]:
    """Load the 50+ labeled intent test cases from JSON fixture."""
    return json.loads(
        (FIXTURES_DIR / "intent_test_cases.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def rag_test_data() -> dict:
    """Load RAG test queries (similarity pairs + quality questions)."""
    return json.loads(
        (FIXTURES_DIR / "rag_test_queries.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def mock_llm_responses() -> dict:
    """Load deterministic mock LLM responses by intent."""
    return json.loads(
        (FIXTURES_DIR / "mock_llm_responses.json").read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# CI artifact output directory
# ---------------------------------------------------------------------------


@pytest.fixture
def artifact_dir(tmp_path: Path) -> Path:
    """CI-aware artifact directory.

    When ``MLOPS_ARTIFACT_DIR`` is set (by the MLOps pipeline), artifacts
    are written to a shared directory so they can be uploaded as GitHub
    Actions artifacts.  Locally, falls back to pytest's ``tmp_path``.
    """
    env_dir = os.environ.get("MLOPS_ARTIFACT_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    return tmp_path


# ---------------------------------------------------------------------------
# Real ML model fixtures (module-scoped to load once)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def intent_classifier():
    """Load the real IntentClassifier with DeBERTa-v3 model.

    Requires: ``transformers``, ``torch`` (ml group).
    """
    from src.services.intent.classifier import IntentClassifier

    return IntentClassifier()


@pytest.fixture(scope="module")
def embedding_service():
    """Load the real EmbeddingService with all-MiniLM-L6-v2 model.

    Requires: ``sentence-transformers``, ``torch`` (ml group).
    """
    from src.services.embedding.embedding_service import EmbeddingService

    return EmbeddingService()
