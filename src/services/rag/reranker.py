"""Cross-encoder reranking service for RAG pipeline.

Reranks documents retrieved by vector similarity using a cross-encoder
model that scores (query, document) pairs directly, improving precision
over embedding-only similarity.
"""

from functools import lru_cache

from src.etl.utils.logger import setup_logger
from src.services.rag.retriever import RetrievedDocument
from src.settings import settings

logger = setup_logger("services.rag.reranker")


class RerankerService:
    """Cross-encoder reranking using sentence-transformers.

    Lazy-loads the model on first call to avoid startup cost
    when reranking is not used.

    Attributes:
        _model_name: HuggingFace cross-encoder model name.
        _top_k: Maximum documents to return after reranking.
        _min_score: Minimum cross-encoder score to keep a document.
    """

    def __init__(
        self,
        model_name: str | None = None,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> None:
        self._model_name = model_name or settings.reranker.model_name
        self._top_k = top_k if top_k is not None else settings.reranker.top_k
        self._min_score = min_score if min_score is not None else settings.reranker.min_score
        self._model = None

    def _load_model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading cross-encoder model: %s", self._model_name)
            self._model = CrossEncoder(self._model_name)
            logger.info("Cross-encoder model loaded")
        return self._model

    def rerank(
        self,
        query: str,
        documents: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        """Rerank documents using cross-encoder scores.

        Args:
            query: User query.
            documents: Documents from vector retrieval.

        Returns:
            Reranked and filtered list of documents (top_k, above min_score).
        """
        if not documents:
            return []

        model = self._load_model()

        # Build (query, document) pairs
        pairs = [(query, doc.content) for doc in documents]

        # Score all pairs
        scores = model.predict(pairs)

        # Attach scores and sort descending
        scored = sorted(
            zip(scores, documents, strict=True),
            key=lambda x: x[0],
            reverse=True,
        )

        # Filter by min_score and limit to top_k
        results = []
        for score, doc in scored:
            if score < self._min_score:
                continue
            doc.rerank_score = float(score)
            results.append(doc)
            if len(results) >= self._top_k:
                break

        logger.info(
            "Reranked %d → %d documents (top_score=%.3f, min_score_threshold=%.1f)",
            len(documents),
            len(results),
            scored[0][0] if scored else 0.0,
            self._min_score,
        )

        return results


@lru_cache(maxsize=1)
def get_reranker_service() -> RerankerService:
    """Get or create singleton RerankerService."""
    return RerankerService()
