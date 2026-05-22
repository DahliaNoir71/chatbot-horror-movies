"""Embedding generation service using sentence-transformers.

Generates 768-dimensional vectors for RAG semantic search.
Model name is sourced from settings.embedding.model_name (env var
EMBEDDING_MODEL_NAME), dimension from EMBEDDING_DIMENSIONS — both
must match the pgvector schema.
"""

from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

from src.etl.utils.logger import setup_logger
from src.settings import settings

EMBEDDING_DIMENSION = settings.embedding.dimensions

# intfloat/multilingual-e5 models require an asymmetric prefix on every input:
# "query: " for search queries, "passage: " for indexed documents. Omitting
# them measurably degrades retrieval — see the model card.
_QUERY_PREFIX = "query: "
_PASSAGE_PREFIX = "passage: "

logger = setup_logger("services.embedding")


class EmbeddingService:
    """Service for generating text embeddings.

    Wraps a sentence-transformers model producing fixed-size vectors
    for pgvector storage. The model is lazy-loaded on first use.

    Attributes:
        model_name: Name of the sentence-transformer model.
        _model: Lazy-loaded transformer model.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """Initialize embedding service.

        Args:
            model_name: Sentence-transformer model name. Defaults to
                settings.embedding.model_name (sourced from .env).
        """
        self._model_name = model_name or settings.embedding.model_name
        self._model = None
        self._logger = logger

    @property
    def model(self):
        """Lazy-load and return the transformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            device = "cpu"
            self._logger.info(f"Loading model: {self._model_name} on {device}")
            self._model = SentenceTransformer(
                self._model_name,
                device=device,
                revision=settings.embedding.revision,
            )
            self._logger.info("Model loaded successfully")
        return self._model

    def generate(self, text: str) -> list[float]:
        """Generate an embedding for a single search query.

        The text is prefixed with the e5 `query:` marker before encoding.

        Args:
            text: Query text to embed.

        Returns:
            List of floats (768 dimensions).
        """
        if not text or not text.strip():
            return self._zero_vector()

        embedding: NDArray[np.float32] = self.model.encode(
            _QUERY_PREFIX + text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embedding.tolist()

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple documents (passages).

        Each non-empty text is prefixed with the e5 `passage:` marker.

        Args:
            texts: List of document texts to embed.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        self._logger.debug(f"Generating embeddings for {len(texts)} texts")
        clean_texts = [_PASSAGE_PREFIX + t if t and t.strip() else "" for t in texts]
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
