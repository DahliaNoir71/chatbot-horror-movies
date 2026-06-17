"""T8 — Embedding quality tests using cosine similarity.

Validates that the configured embedding model produces semantically
coherent embeddings: similar queries should be close, dissimilar far apart.

Requires: ``ml-api`` dependency group (sentence-transformers, torch).
Run with: ``uv run --group ml-api pytest tests/model/test_embedding_quality.py -m model -v``
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


def _pair_similarities(service, pairs: list[dict]) -> list[float]:
    """Cosine similarity for each (query_a, query_b) pair via the query path."""
    sims = []
    for pair in pairs:
        vec_a = service.generate(pair["query_a"])
        vec_b = service.generate(pair["query_b"])
        sims.append(_cosine_similarity(vec_a, vec_b))
    return sims


# =========================================================================
# T8 — Cosine similarity coherence
# =========================================================================


@pytest.mark.model
@pytest.mark.slow
class TestEmbeddingSimilarity:
    """T8 — Validate semantic coherence of embedding vectors."""

    @staticmethod
    def test_related_pairs_rank_above_unrelated(embedding_service, rag_test_data):
        """Related query pairs all score above every unrelated pair.

        Replaces absolute, model-specific thresholds with the property that
        retrieval actually depends on: related queries rank above unrelated
        ones, regardless of the model's absolute similarity scale (e5 has a much
        higher similarity floor than the previous MiniLM model, which broke the
        old hard-coded thresholds).
        """
        related = _pair_similarities(
            embedding_service, rag_test_data["similarity_pairs"]
        )
        unrelated = _pair_similarities(
            embedding_service, rag_test_data["dissimilar_pairs"]
        )
        min_related = min(related)
        max_unrelated = max(unrelated)

        assert min_related > max_unrelated, (
            f"No topical separation: weakest related pair ({min_related:.3f}) "
            f"does not exceed strongest unrelated pair ({max_unrelated:.3f})"
        )


# =========================================================================
# T8 — Embedding properties with real model
# =========================================================================


@pytest.mark.model
@pytest.mark.slow
class TestEmbeddingProperties:
    """T8 — Verify real model embedding properties."""

    @staticmethod
    def test_embedding_dimension_matches_settings(embedding_service):
        """Real model produces vectors of the configured dimension."""
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
    @pytest.mark.slow
    def test_batch_consistency(embedding_service):
        """Batched passage embeddings match single-passage encodings.

        Holds the e5 ``passage:`` prefix constant and varies only batch size:
        a text encoded alone must match its slot in a multi-text batch (padding
        must not alter the result). Comparing against ``generate`` (the query
        path) would falsely fail, since e5's query/passage prefixes are
        asymmetric by design.
        """
        texts = [
            "zombie apocalypse horror film",
            "a quiet psychological ghost story set in an old manor",
            "slasher",
        ]

        single = [embedding_service.generate_batch([t])[0] for t in texts]
        batch = embedding_service.generate_batch(texts)

        for i, (one, many) in enumerate(zip(single, batch)):
            sim = _cosine_similarity(one, many)
            assert sim > 0.99, (
                f"Batch vs single mismatch for text {i}: similarity={sim:.4f}"
            )
