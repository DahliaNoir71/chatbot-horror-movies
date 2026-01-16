"""RAG importer for loading aggregated films into vector store.

Reads JSON from aggregation pipeline, generates embeddings,
and inserts into horrorbot_vectors.rag_documents table.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.database.importer.embedding_service import (
    EmbeddingService,
    get_embedding_service,
)
from src.etl.utils.logger import setup_logger
from src.settings import settings

logger = setup_logger("database.importer.rag")

# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_INPUT_PATH = Path("data/processed/rag_films.json")
BATCH_SIZE = 50


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class RAGDocument:
    """Document prepared for RAG insertion.

    Attributes:
        content: Text content for embedding.
        source_type: Document type (film_overview, critics_consensus).
        source_id: TMDB film ID.
        metadata: Additional searchable metadata.
    """

    content: str
    source_type: str
    source_id: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGImportResult:
    """Results from RAG import execution.

    Attributes:
        films_processed: Number of films read from JSON.
        documents_created: Total documents inserted.
        overviews_count: Film overview documents.
        consensus_count: Critics consensus documents.
        duration_seconds: Total execution time.
        errors: List of error messages.
    """

    films_processed: int = 0
    documents_created: int = 0
    overviews_count: int = 0
    consensus_count: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


# =============================================================================
# RAG IMPORTER
# =============================================================================


class RAGImporter:
    """Imports aggregated films into RAG vector store.

    Reads rag_films.json, generates embeddings using
    sentence-transformers, and bulk inserts into
    horrorbot_vectors.rag_documents.

    Usage:
        importer = RAGImporter()
        result = importer.run()
    """

    def __init__(
        self,
        input_path: Path | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize RAG importer.

        Args:
            input_path: Path to rag_films.json.
            embedding_service: Optional embedding service instance.
        """
        self._input_path = input_path or DEFAULT_INPUT_PATH
        self._embedding_service = embedding_service or get_embedding_service()
        self._logger = logger
        self._session: Session | None = None

    # =========================================================================
    # Public API
    # =========================================================================

    def run(self, clear_existing: bool = False) -> RAGImportResult:
        """Execute RAG import pipeline.

        Args:
            clear_existing: If True, delete existing documents first.

        Returns:
            RAGImportResult with statistics.
        """
        start_time = datetime.now()
        result = RAGImportResult()

        self._log_start()

        try:
            result = self._execute_import(clear_existing)
        except Exception as e:
            self._logger.error(f"Import failed: {e}")
            result.errors.append(str(e))

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        self._log_results(result)

        return result

    # =========================================================================
    # Import Execution
    # =========================================================================

    def _execute_import(self, clear_existing: bool) -> RAGImportResult:
        """Execute import stages.

        Args:
            clear_existing: Whether to clear existing documents.

        Returns:
            Import result with statistics.
        """
        result = RAGImportResult()

        # Stage 1: Load JSON
        films = self._load_json()
        result.films_processed = len(films)

        if not films:
            self._logger.warning("No films found in JSON")
            return result

        # Stage 2: Prepare documents
        documents = self._prepare_documents(films)
        result.overviews_count = self._count_by_type(documents, "film_overview")
        result.consensus_count = self._count_by_type(documents, "critics_consensus")

        # Stage 3: Preload embedding model
        self._logger.info("Stage 3: Loading embedding model...")
        _ = self._embedding_service.model
        self._logger.info("Embedding model ready")

        # Stage 4: Generate embeddings and insert
        session = self._get_vectors_session()

        if clear_existing:
            self._clear_documents(session)

        result.documents_created = self._insert_documents(session, documents)
        session.commit()
        self._logger.info("Database commit complete")

        return result

    def _load_json(self) -> list[dict[str, Any]]:
        """Load films from JSON file.

        Returns:
            List of film dictionaries.
        """
        self._logger.info(f"Stage 1: Loading JSON from {self._input_path}")

        if not self._input_path.exists():
            raise FileNotFoundError(f"JSON not found: {self._input_path}")

        with self._input_path.open(encoding="utf-8") as f:
            data = json.load(f)

        films = data.get("films", [])
        self._logger.info(f"Loaded {len(films)} films from JSON")

        return films

    # =========================================================================
    # Document Preparation
    # =========================================================================

    def _prepare_documents(
        self,
        films: list[dict[str, Any]],
    ) -> list[RAGDocument]:
        """Prepare RAG documents from films.

        Args:
            films: Film data from JSON.

        Returns:
            List of RAGDocument instances.
        """
        self._logger.info("Stage 2: Preparing RAG documents...")
        documents: list[RAGDocument] = []

        for film in films:
            documents.extend(self._film_to_documents(film))

        self._logger.info(f"Prepared {len(documents)} documents")
        return documents

    def _film_to_documents(self, film: dict[str, Any]) -> list[RAGDocument]:
        """Convert film to RAG documents.

        Args:
            film: Film dictionary.

        Returns:
            List of documents (overview and/or consensus).
        """
        documents: list[RAGDocument] = []
        tmdb_id = film.get("tmdb_id", 0)
        metadata = self._build_metadata(film)

        overview_doc = self._create_overview_doc(film, tmdb_id, metadata)
        if overview_doc:
            documents.append(overview_doc)

        consensus_doc = self._create_consensus_doc(film, tmdb_id, metadata)
        if consensus_doc:
            documents.append(consensus_doc)

        return documents

    @staticmethod
    def _create_overview_doc(
        film: dict[str, Any],
        tmdb_id: int,
        metadata: dict[str, Any],
    ) -> RAGDocument | None:
        """Create document from film overview.

        Args:
            film: Film dictionary.
            tmdb_id: TMDB identifier.
            metadata: Document metadata.

        Returns:
            RAGDocument or None if no overview.
        """
        overview = film.get("overview")
        if not overview or not overview.strip():
            return None

        return RAGDocument(
            content=overview.strip(),
            source_type="film_overview",
            source_id=tmdb_id,
            metadata=metadata,
        )

    @staticmethod
    def _create_consensus_doc(
        film: dict[str, Any],
        tmdb_id: int,
        metadata: dict[str, Any],
    ) -> RAGDocument | None:
        """Create document from critics consensus.

        Args:
            film: Film dictionary.
            tmdb_id: TMDB identifier.
            metadata: Document metadata.

        Returns:
            RAGDocument or None if no consensus.
        """
        consensus = film.get("critics_consensus")
        if not consensus or not consensus.strip():
            return None

        return RAGDocument(
            content=consensus.strip(),
            source_type="critics_consensus",
            source_id=tmdb_id,
            metadata=metadata,
        )

    @staticmethod
    def _build_metadata(film: dict[str, Any]) -> dict[str, Any]:
        """Build metadata dictionary for document.

        Args:
            film: Film dictionary.

        Returns:
            Metadata for JSONB storage.
        """
        return {
            "title": film.get("title", ""),
            "year": film.get("release_date", "")[:4] if film.get("release_date") else None,
            "genres": film.get("genres", []),
            "vote_average": film.get("vote_average", 0),
            "tomatometer": film.get("tomatometer_score"),
        }

    @staticmethod
    def _count_by_type(documents: list[RAGDocument], source_type: str) -> int:
        """Count documents by source type.

        Args:
            documents: List of documents.
            source_type: Type to count.

        Returns:
            Count of matching documents.
        """
        return sum(1 for d in documents if d.source_type == source_type)

    # =========================================================================
    # Database Operations
    # =========================================================================

    def _insert_documents(
        self,
        session: Session,
        documents: list[RAGDocument],
    ) -> int:
        """Insert documents with embeddings in batches.

        Args:
            session: Database session.
            documents: Documents to insert.

        Returns:
            Number of documents inserted.
        """
        total = len(documents)
        batches = list(self._batch_documents(documents))
        total_batches = len(batches)

        self._logger.info(f"Stage 4: Inserting {total} documents in {total_batches} batches...")
        inserted = 0

        for i, batch in enumerate(batches, 1):
            batch_inserted = self._insert_batch(session, batch)
            inserted += batch_inserted

            if i % 10 == 0 or i == total_batches:
                pct = (inserted / total) * 100
                self._logger.info(
                    f"Progress: {i}/{total_batches} batches, {inserted}/{total} docs ({pct:.1f}%)"
                )

        return inserted

    def _insert_batch(
        self,
        session: Session,
        documents: list[RAGDocument],
    ) -> int:
        """Insert a batch of documents.

        Args:
            session: Database session.
            documents: Batch of documents.

        Returns:
            Number of documents inserted.
        """
        # Generate embeddings for batch
        texts = [d.content for d in documents]
        embeddings = self._embedding_service.generate_batch(texts)

        # Bulk insert
        values = []
        for doc, embedding in zip(documents, embeddings, strict=True):
            values.append(
                {
                    "id": str(uuid4()),
                    "content": doc.content,
                    "embedding": embedding,
                    "source_type": doc.source_type,
                    "source_id": doc.source_id,
                    "metadata": json.dumps(doc.metadata),
                }
            )

        self._bulk_insert(session, values)
        return len(documents)

    @staticmethod
    def _bulk_insert(session: Session, values: list[dict[str, Any]]) -> None:
        """Execute bulk insert with upsert.

        Args:
            session: Database session.
            values: List of row dictionaries.
        """
        if not values:
            return

        # Build bulk VALUES clause
        placeholders = []
        params: dict[str, Any] = {}

        for i, row in enumerate(values):
            placeholders.append(
                f"(:id_{i}, :content_{i}, CAST(:embedding_{i} AS vector), "
                f":source_type_{i}, :source_id_{i}, CAST(:metadata_{i} AS jsonb), 0, 1)"
            )
            params[f"id_{i}"] = row["id"]
            params[f"content_{i}"] = row["content"]
            params[f"embedding_{i}"] = str(row["embedding"])
            params[f"source_type_{i}"] = row["source_type"]
            params[f"source_id_{i}"] = row["source_id"]
            params[f"metadata_{i}"] = row["metadata"]

        stmt = text(f"""
            INSERT INTO rag_documents (
                id, content, embedding, source_type,
                source_id, metadata, chunk_index, chunk_total
            ) VALUES {", ".join(placeholders)}
            ON CONFLICT (source_type, source_id, chunk_index)
            DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
        """)

        session.execute(stmt, params)
        session.flush()

    def _clear_documents(self, session: Session) -> None:
        """Delete all existing RAG documents.

        Args:
            session: Database session.
        """
        self._logger.info("Clearing existing documents...")
        session.execute(text("TRUNCATE TABLE rag_documents"))
        session.flush()

    @staticmethod
    def _batch_documents(
        documents: list[RAGDocument],
    ) -> list[list[RAGDocument]]:
        """Split documents into batches.

        Args:
            documents: All documents.

        Returns:
            List of document batches.
        """
        return [documents[i : i + BATCH_SIZE] for i in range(0, len(documents), BATCH_SIZE)]

    # =========================================================================
    # Session Management
    # =========================================================================

    def _get_vectors_session(self) -> Session:
        """Get session for vectors database.

        Returns:
            SQLAlchemy session for horrorbot_vectors.
        """
        if self._session is None:
            engine = create_engine(settings.database.vectors_sync_url)
            session_factory = sessionmaker(bind=engine)
            self._session = session_factory()
        return self._session

    # =========================================================================
    # Logging
    # =========================================================================

    def _log_start(self) -> None:
        """Log import start."""
        self._logger.info("=" * 60)
        self._logger.info("Starting RAG Import")
        self._logger.info("=" * 60)
        self._logger.info(f"Input: {self._input_path}")
        self._logger.info(f"Model: {self._embedding_service.model_name}")

    def _log_results(self, result: RAGImportResult) -> None:
        """Log import results.

        Args:
            result: Import result.
        """
        self._logger.info("=" * 60)
        self._logger.info("RAG Import Complete")
        self._logger.info("=" * 60)
        self._logger.info(f"Films processed: {result.films_processed}")
        self._logger.info(f"Documents created: {result.documents_created}")
        self._logger.info(f"  - Overviews: {result.overviews_count}")
        self._logger.info(f"  - Consensus: {result.consensus_count}")
        self._logger.info(f"Duration: {result.duration_seconds:.1f}s")


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================


def run_rag_import(
    input_path: Path | None = None,
    clear_existing: bool = False,
) -> RAGImportResult:
    """Run RAG import pipeline.

    Args:
        input_path: Path to rag_films.json.
        clear_existing: Clear existing documents first.

    Returns:
        RAGImportResult with statistics.
    """
    importer = RAGImporter(input_path=input_path)
    return importer.run(clear_existing=clear_existing)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main() -> None:
    """Entry point for RAG import."""
    import argparse

    parser = argparse.ArgumentParser(description="RAG Import Pipeline")
    parser.add_argument("--input", type=str, help="Input JSON path")
    parser.add_argument("--clear", action="store_true", help="Clear existing")

    args = parser.parse_args()

    input_path = Path(args.input) if args.input else None
    result = run_rag_import(input_path=input_path, clear_existing=args.clear)

    print(f"\nFilms: {result.films_processed}")
    print(f"Documents: {result.documents_created}")
    print(f"Duration: {result.duration_seconds:.1f}s")


if __name__ == "__main__":
    main()
