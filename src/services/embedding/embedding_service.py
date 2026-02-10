"""Embedding generation service using sentence-transformers.

Generates 384-dimensional vectors for RAG semantic search.
"""

from functools import lru_cache

import numpy as np
from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer

from src.etl.utils.logger import setup_logger

# Model producing 384-dim embeddings (matches pgvector schema)
DEFAULT_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

logger = setup_logger("services.embedding")


class EmbeddingService:
    """Service for generating text embeddings.

    Uses sentence-transformers with all-MiniLM-L6-v2 model
    producing 384-dimensional vectors for pgvector storage.

    Attributes:
        model_name: Name of the sentence-transformer model.
        _model: Lazy-loaded transformer model.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        """Initialize embedding service.

        Args:
            model_name: Sentence-transformer model name.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._logger = logger

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load and return the transformer model."""
        if self._model is None:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._logger.info(f"Loading model: {self._model_name} on {device}")
            self._model = SentenceTransformer(self._model_name, device=device)
            self._logger.info("Model loaded successfully")
        return self._model

    def generate(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed.

        Returns:
            List of floats (384 dimensions).
        """
        if not text or not text.strip():
            return self._zero_vector()

        embedding: NDArray[np.float32] = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embedding.tolist()

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        self._logger.debug(f"Generating embeddings for {len(texts)} texts")
        clean_texts = [t if t and t.strip() else "" for t in texts]
        embeddings: NDArray[np.float32] = self.model.encode(
            clean_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    @staticmethod
    def _zero_vector() -> list[float]:
        """Return zero vector for empty texts."""
        return [0.0] * EMBEDDING_DIMENSION

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return EMBEDDING_DIMENSION

    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._model_name


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Get singleton embedding service instance.

    Returns:
        Cached EmbeddingService instance.
    """
    return EmbeddingService()
