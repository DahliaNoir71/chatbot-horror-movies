"""Hybrid retrieval configuration.

Controls BM25/vector fusion weights, RRF constant, popularity boost,
rerank confidence threshold, and per-list top-K caps. Consumed by
`HybridRetriever` and `RAGPipeline`.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrievalSettings(BaseSettings):
    """Hybrid retrieval configuration.

    Attributes:
        vector_weight: RRF weight for the vector retrieval list.
        bm25_weight: RRF weight for the BM25 retrieval list.
        rrf_k: Reciprocal Rank Fusion constant — higher dampens top-rank dominance.
        vector_top_k: Max documents fetched from the vector store per query.
        bm25_top_k: Max documents fetched from BM25 per query.
        final_top_k: Default number of documents returned by `HybridRetriever.search`.
        min_similarity: Vector store similarity threshold (filters noise in
            the embedding retriever).
        min_rerank_score: Cross-encoder rerank score below which a document
            is dropped to prevent LLM hallucinations.
        popularity_weight: Scale applied to the popularity boost. RRF scores
            are ~0.01–0.05 while normalized popularity is in ~[0, 1.4], so a
            calibrated value is typically in the 0.001–0.01 range.
    """

    vector_weight: float = Field(default=0.5, alias="RETRIEVAL_VECTOR_WEIGHT")
    bm25_weight: float = Field(default=0.5, alias="RETRIEVAL_BM25_WEIGHT")
    rrf_k: int = Field(default=60, alias="RETRIEVAL_RRF_K")
    vector_top_k: int = Field(default=20, alias="RETRIEVAL_VECTOR_TOP_K")
    bm25_top_k: int = Field(default=20, alias="RETRIEVAL_BM25_TOP_K")
    final_top_k: int = Field(default=5, alias="RETRIEVAL_FINAL_TOP_K")
    min_similarity: float = Field(default=0.3, alias="RETRIEVAL_MIN_SIMILARITY")
    min_rerank_score: float = Field(default=-2.0, alias="RETRIEVAL_MIN_RERANK_SCORE")
    popularity_weight: float = Field(default=0.15, alias="RETRIEVAL_POPULARITY_WEIGHT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("rrf_k", "vector_top_k", "bm25_top_k", "final_top_k")
    @classmethod
    def _positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be > 0")
        return v

    @field_validator("min_similarity", "popularity_weight", "vector_weight", "bm25_weight")
    @classmethod
    def _non_negative_float(cls, v: float) -> float:
        if v < 0:
            raise ValueError("must be >= 0")
        return v
