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
        rerank_pool_top_k: Number of fused candidates the cross-encoder reranks.
            Wide (30) so thematic classics the popularity prior ranked 6-30 still
            reach the reranker. Safe because the FINAL order blends the rerank
            score with the RRF+popularity prior (see rerank_blend_weight): without
            that blend a wide pool lets the lexically-biased cross-encoder bury
            thematic films (e.g. "The Thing" under "Body Snatcher" for "body
            horror" — observed 2026-06-16, pool 30 pure-rerank → 0/5 grounding).
        rerank_blend_weight: Weight of the cross-encoder rerank vs the
            RRF+popularity prior when ordering the reranked pool (RRF rank
            fusion). 1.0 = pure rerank (lexically biased on thematic queries),
            0.0 = pure prior (ignores the cross-encoder), 0.5 = balanced. A/B on
            real queries before changing.
        min_similarity: Vector store similarity threshold (filters noise in
            the embedding retriever).
        min_rerank_score: Cross-encoder rerank score below which a document
            is dropped to prevent LLM hallucinations.
        open_fallback_enabled: When no document clears the rerank threshold,
            answer from the LLM's general knowledge (clearly labelled as
            unverified) instead of returning the templated refusal. True =
            demo's "open" behaviour; False = strict anti-hallucination refusal.
        popularity_weight: Scale applied to the popularity boost. RRF scores
            are ~0.01–0.05 while normalized popularity is in ~[0, 1.4], so a
            calibrated value is typically in the 0.001–0.02 range.
    """

    vector_weight: float = Field(default=0.5, alias="RETRIEVAL_VECTOR_WEIGHT")
    bm25_weight: float = Field(default=0.5, alias="RETRIEVAL_BM25_WEIGHT")
    rrf_k: int = Field(default=60, alias="RETRIEVAL_RRF_K")
    vector_top_k: int = Field(default=50, alias="RETRIEVAL_VECTOR_TOP_K")
    bm25_top_k: int = Field(default=20, alias="RETRIEVAL_BM25_TOP_K")
    final_top_k: int = Field(default=5, alias="RETRIEVAL_FINAL_TOP_K")
    rerank_pool_top_k: int = Field(default=30, alias="RETRIEVAL_RERANK_POOL_TOP_K")
    rerank_blend_weight: float = Field(default=0.5, alias="RETRIEVAL_RERANK_BLEND_WEIGHT")
    min_similarity: float = Field(default=0.3, alias="RETRIEVAL_MIN_SIMILARITY")
    min_rerank_score: float = Field(default=-5.0, alias="RETRIEVAL_MIN_RERANK_SCORE")
    popularity_weight: float = Field(default=0.02, alias="RETRIEVAL_POPULARITY_WEIGHT")
    open_fallback_enabled: bool = Field(default=True, alias="RAG_OPEN_FALLBACK_ENABLED")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("rrf_k", "vector_top_k", "bm25_top_k", "final_top_k", "rerank_pool_top_k")
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

    @field_validator("rerank_blend_weight")
    @classmethod
    def _unit_interval(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("RETRIEVAL_RERANK_BLEND_WEIGHT must be between 0.0 and 1.0")
        return v
