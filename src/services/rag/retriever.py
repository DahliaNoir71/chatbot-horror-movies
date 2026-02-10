"""RAG document retriever using pgvector similarity search.

Queries the horrorbot_vectors database for semantically similar
documents using the search_similar_documents() SQL function.
"""

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.etl.utils.logger import setup_logger
from src.monitoring.metrics import (
    EMBEDDING_REQUEST_DURATION,
    RAG_DOCUMENTS_RETRIEVED,
    RAG_RETRIEVAL_DURATION,
    RAG_TOP_SIMILARITY,
)
from src.services.embedding.embedding_service import get_embedding_service
from src.settings import settings

logger = setup_logger("services.rag.retriever")


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class RetrievedDocument:
    """Document returned from similarity search.

    Attributes:
        id: Document UUID.
        content: Text content of the chunk.
        source_type: Origin type (film_overview, critics_consensus).
        source_id: TMDB film ID.
        metadata: JSONB metadata (title, year, genres, etc.).
        similarity: Cosine similarity score (0.0-1.0).
    """

    id: UUID
    content: str
    source_type: str
    source_id: int
    metadata: dict[str, Any]
    similarity: float


# =============================================================================
# DOCUMENT RETRIEVER
# =============================================================================


class DocumentRetriever:
    """Retrieves relevant documents from the vector store.

    Uses EmbeddingService to encode queries and the
    search_similar_documents() SQL function for similarity search.

    Attributes:
        _engine: SQLAlchemy engine for vectors database.
        _session_factory: Session factory for vectors database.
        _embedding_service: Service for generating query embeddings.
        _default_match_count: Default number of results to return.
        _default_threshold: Default similarity threshold.
    """

    def __init__(
        self,
        match_count: int = 5,
        similarity_threshold: float = 0.7,
    ) -> None:
        """Initialize retriever.

        Args:
            match_count: Default maximum documents to retrieve.
            similarity_threshold: Minimum cosine similarity (0.0-1.0).
        """
        self._embedding_service = get_embedding_service()
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None
        self._default_match_count = match_count
        self._default_threshold = similarity_threshold
        self._logger = logger

    def _get_engine(self) -> Engine:
        """Lazy-create engine for vectors database."""
        if self._engine is None:
            self._engine = create_engine(
                settings.database.vectors_sync_url,
                pool_size=settings.database.pool_size,
                max_overflow=settings.database.pool_overflow,
                pool_pre_ping=True,
            )
        return self._engine

    def _get_session(self) -> Session:
        """Get a new session for the vectors database."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self._get_engine(),
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory()

    def retrieve(
        self,
        query: str,
        match_count: int | None = None,
        similarity_threshold: float | None = None,
        source_type: str | None = None,
    ) -> list[RetrievedDocument]:
        """Retrieve similar documents for a query.

        Args:
            query: User query text.
            match_count: Override default match count.
            similarity_threshold: Override default threshold.
            source_type: Filter by source_type (film_overview, critics_consensus).

        Returns:
            List of RetrievedDocument ordered by descending similarity.
        """
        count = match_count or self._default_match_count
        threshold = similarity_threshold or self._default_threshold

        embed_start = time.perf_counter()
        query_embedding = self._embedding_service.generate(query)
        embed_duration = time.perf_counter() - embed_start
        EMBEDDING_REQUEST_DURATION.observe(embed_duration)

        retrieval_start = time.perf_counter()
        documents = self._execute_search(
            query_embedding,
            count,
            threshold,
            source_type,
        )
        retrieval_duration = time.perf_counter() - retrieval_start

        RAG_RETRIEVAL_DURATION.observe(retrieval_duration)
        RAG_DOCUMENTS_RETRIEVED.observe(len(documents))
        if documents:
            RAG_TOP_SIMILARITY.observe(documents[0].similarity)

        self._logger.debug(
            f"Retrieval complete: found {len(documents)} documents "
            f"(query: {query[:80]}, duration: {round(retrieval_duration * 1000)}ms)"
        )

        return documents

    def _execute_search(
        self,
        embedding: list[float],
        match_count: int,
        threshold: float,
        source_type: str | None,
    ) -> list[RetrievedDocument]:
        """Execute the search_similar_documents SQL function.

        Args:
            embedding: Query embedding vector.
            match_count: Maximum results.
            threshold: Minimum similarity.
            source_type: Optional source type filter.

        Returns:
            List of RetrievedDocument.
        """
        session = self._get_session()
        try:
            sql = text(
                "SELECT * FROM search_similar_documents("
                "(:query_embedding)::vector, :match_count, :threshold, :source_type"
                ")"
            )
            result = session.execute(
                sql,
                {
                    "query_embedding": str(embedding),
                    "match_count": match_count,
                    "threshold": threshold,
                    "source_type": source_type,
                },
            )
            return [
                RetrievedDocument(
                    id=row.id,
                    content=row.content,
                    source_type=row.source_type,
                    source_id=row.source_id,
                    metadata=row.metadata if isinstance(row.metadata, dict) else {},
                    similarity=float(row.similarity),
                )
                for row in result
            ]
        finally:
            session.close()


# =============================================================================
# SINGLETON
# =============================================================================


@lru_cache(maxsize=1)
def get_document_retriever() -> DocumentRetriever:
    """Get singleton DocumentRetriever instance.

    Returns:
        Cached DocumentRetriever instance.
    """
    return DocumentRetriever()
