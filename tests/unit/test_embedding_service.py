"""T6 — Unit tests for EmbeddingService.

Uses mocked SentenceTransformer to avoid loading the real model in CI.
Tests dimensions, normalization, batch generation, and edge cases.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from pytest import approx

from src.services.embedding.embedding_service import (
    DEFAULT_MODEL,
    EMBEDDING_DIMENSION,
    EmbeddingService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_model():
    """Mock SentenceTransformer model with deterministic encode()."""
    mock = MagicMock()
    # Single text: return a normalized 384-dim vector
    single_vector = np.random.default_rng(42).random(384, dtype=np.float32)
    single_vector /= np.linalg.norm(single_vector)
    mock.encode.return_value = single_vector
    return mock


@pytest.fixture
def embedding_service(mock_model) -> EmbeddingService:
    """EmbeddingService with pre-injected mock model."""
    service = EmbeddingService(model_name="mock-model")
    service._model = mock_model
    return service


# =========================================================================
# T6 — generate() single text
# =========================================================================


class TestEmbeddingServiceGenerate:
    """T6 — Single text embedding generation."""

    @staticmethod
    def test_returns_list_of_floats(embedding_service):
        """generate() returns a plain list of floats."""
        result = embedding_service.generate("horror movie")

        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    @staticmethod
    def test_dimension_is_384(embedding_service):
        """Output vector has 384 dimensions."""
        result = embedding_service.generate("test text")

        assert len(result) == EMBEDDING_DIMENSION

    @staticmethod
    def test_empty_text_returns_zero_vector(embedding_service):
        """Empty string returns a zero vector without calling the model."""
        result = embedding_service.generate("")

        assert result == [0.0] * EMBEDDING_DIMENSION
        embedding_service._model.encode.assert_not_called()

    @staticmethod
    def test_whitespace_returns_zero_vector(embedding_service):
        """Whitespace-only text returns a zero vector."""
        result = embedding_service.generate("   ")

        assert result == [0.0] * EMBEDDING_DIMENSION

    @staticmethod
    def test_none_returns_zero_vector(embedding_service):
        """None text returns a zero vector."""
        result = embedding_service.generate(None)

        assert result == [0.0] * EMBEDDING_DIMENSION

    @staticmethod
    def test_calls_model_encode_with_normalize(embedding_service, mock_model):
        """encode() is called with normalize_embeddings=True."""
        embedding_service.generate("test query")

        mock_model.encode.assert_called_once()
        call_kwargs = mock_model.encode.call_args
        assert call_kwargs.kwargs.get("normalize_embeddings") is True
        assert call_kwargs.kwargs.get("convert_to_numpy") is True


# =========================================================================
# T6 — generate_batch()
# =========================================================================


class TestEmbeddingServiceBatch:
    """T6 — Batch embedding generation."""

    @staticmethod
    def test_batch_returns_list_of_lists(embedding_service, mock_model):
        """generate_batch() returns a list of embedding vectors."""
        batch_result = np.random.default_rng(42).random((3, 384), dtype=np.float32)
        mock_model.encode.return_value = batch_result

        result = embedding_service.generate_batch(["text1", "text2", "text3"])

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(len(vec) == 384 for vec in result)

    @staticmethod
    def test_empty_list_returns_empty(embedding_service):
        """Empty input list returns empty output."""
        result = embedding_service.generate_batch([])

        assert result == []

    @staticmethod
    def test_handles_mixed_empty_texts(embedding_service, mock_model):
        """Batch with empty/None texts replaces them with empty strings."""
        batch_result = np.random.default_rng(42).random((3, 384), dtype=np.float32)
        mock_model.encode.return_value = batch_result

        result = embedding_service.generate_batch(["valid", "", "  "])

        assert len(result) == 3
        # Verify the clean_texts logic: empty/whitespace replaced with ""
        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["valid", "", ""]


# =========================================================================
# T6 — Properties
# =========================================================================


class TestEmbeddingServiceProperties:
    """T6 — Service properties and lazy loading."""

    @staticmethod
    def test_dimension_property():
        """dimension property returns EMBEDDING_DIMENSION (384)."""
        service = EmbeddingService()
        assert service.dimension == 384

    @staticmethod
    def test_model_name_property():
        """model_name returns the configured model name."""
        service = EmbeddingService(model_name="custom-model")
        assert service.model_name == "custom-model"

    @staticmethod
    def test_default_model_name():
        """Default model is all-MiniLM-L6-v2."""
        service = EmbeddingService()
        assert service.model_name == DEFAULT_MODEL

    @staticmethod
    def test_model_lazy_loaded():
        """Model is not loaded at __init__ time."""
        service = EmbeddingService()
        assert service._model is None

    @staticmethod
    def test_zero_vector_dimension():
        """_zero_vector() returns correct dimension."""
        vec = EmbeddingService._zero_vector()
        assert len(vec) == EMBEDDING_DIMENSION
        assert all(x == approx(0.0) for x in vec)
