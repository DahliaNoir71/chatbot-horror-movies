"""T8 — Embedding quality tests using cosine similarity.

Validates that the real all-MiniLM-L6-v2 model produces semantically
coherent embeddings: similar queries should be close, dissimilar far apart.

Requires: ``ml`` dependency group (sentence-transformers, torch).
Run with: ``uv run --group ml pytest tests/model/test_embedding_quality.py -m model -v``
"""

from __future__ import annotations

import math

import pytest
from pytest import approx

from src.services.embedding.embedding_service import EMBEDDING_DIMENSION


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# =========================================================================
# T8 — Cosine similarity coherence
# =========================================================================


@pytest.mark.model
class TestEmbeddingSimilarity:
    """T8 — Validate semantic coherence of embedding vectors."""

    @staticmethod
    def test_similar_queries_high_similarity(embedding_service, rag_test_data):
        """Similar query pairs have cosine similarity above their threshold."""
        failures = []

        for pair in rag_test_data["similarity_pairs"]:
            vec_a = embedding_service.generate(pair["query_a"])
            vec_b = embedding_service.generate(pair["query_b"])
            similarity = _cosine_similarity(vec_a, vec_b)

            if similarity < pair["expected_min_similarity"]:
                failures.append(
                    f"  sim={similarity:.3f} < {pair['expected_min_similarity']} "
                    f"| '{pair['query_a']}' vs '{pair['query_b']}'"
                )

        assert len(failures) == 0, (
            f"{len(failures)} similar pairs below threshold:\n" + "\n".join(failures)
        )

    @staticmethod
    def test_dissimilar_queries_low_similarity(embedding_service, rag_test_data):
        """Dissimilar query pairs have cosine similarity below their threshold."""
        failures = []

        for pair in rag_test_data["dissimilar_pairs"]:
            vec_a = embedding_service.generate(pair["query_a"])
            vec_b = embedding_service.generate(pair["query_b"])
            similarity = _cosine_similarity(vec_a, vec_b)

            if similarity > pair["expected_max_similarity"]:
                failures.append(
                    f"  sim={similarity:.3f} > {pair['expected_max_similarity']} "
                    f"| '{pair['query_a']}' vs '{pair['query_b']}'"
                )

        assert len(failures) == 0, (
            f"{len(failures)} dissimilar pairs above threshold:\n" + "\n".join(failures)
        )


# =========================================================================
# T8 — Embedding properties with real model
# =========================================================================


@pytest.mark.model
class TestEmbeddingProperties:
    """T8 — Verify real model embedding properties."""

    @staticmethod
    def test_embedding_dimension_384(embedding_service):
        """Real model produces 384-dimensional vectors."""
        vec = embedding_service.generate("test horror movie query")
        assert len(vec) == EMBEDDING_DIMENSION

    @staticmethod
    def test_embeddings_are_normalized(embedding_service):
        """Embeddings are L2-normalized (norm ≈ 1.0)."""
        vec = embedding_service.generate("The Shining is a terrifying masterpiece")
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 0.01, f"Norm {norm:.4f} is not close to 1.0"

    @staticmethod
    def test_identical_texts_produce_identical_embeddings(embedding_service):
        """Same text encoded twice produces identical vectors."""
        text = "Recommend me a horror film like Hereditary"
        vec1 = embedding_service.generate(text)
        vec2 = embedding_service.generate(text)
        similarity = _cosine_similarity(vec1, vec2)
        assert similarity > 0.999, f"Same text similarity {similarity:.4f} < 0.999"

    @staticmethod
    def test_empty_text_returns_zero_vector(embedding_service):
        """Empty text returns a zero vector (not a model-generated one)."""
        vec = embedding_service.generate("")
        assert all(x == approx(0.0) for x in vec)
        assert len(vec) == EMBEDDING_DIMENSION

    @staticmethod
    def test_batch_consistency(embedding_service):
        """Batch-generated embeddings match individually-generated ones."""
        texts = [
            "zombie apocalypse horror film",
            "haunted house ghost story",
        ]

        individual = [embedding_service.generate(t) for t in texts]
        batch = embedding_service.generate_batch(texts)

        for i, (ind, bat) in enumerate(zip(individual, batch)):
            sim = _cosine_similarity(ind, bat)
            assert sim > 0.99, (
                f"Batch vs individual mismatch for text {i}: similarity={sim:.4f}"
            )
