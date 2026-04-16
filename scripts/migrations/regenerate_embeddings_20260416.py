"""Hash-based incremental embedding regeneration (2026-04-16).

For every row in `horrorbot_vectors.rag_documents`, rebuild the `content`
from the **current** state of `horrorbot.films` using the bilingual
RAGImporter logic (post-0.A.4), compare its MD5 against the stored
`content_hash`, and regenerate the embedding only when the hash differs.

First run regenerates everything because `content_hash` is NULL across
the corpus after the 0.A.1 schema migration. Subsequent runs become
incremental: only films whose content actually changed get re-embedded.

Invocation:

    python -m scripts.migrations.regenerate_embeddings_20260416 --dry-run --limit 1000
    python -m scripts.migrations.regenerate_embeddings_20260416 --limit 1000
    python -m scripts.migrations.regenerate_embeddings_20260416 --source-type film_overview
    python -m scripts.migrations.regenerate_embeddings_20260416  # full run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.database.importer.rag_importer import RAGImporter
from src.services.embedding.embedding_service import (
    EmbeddingService,
    get_embedding_service,
)
from src.settings import settings

logger = logging.getLogger("scripts.migrations.regenerate_embeddings")

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

DEFAULT_BATCH_SIZE = 128
LOG_INTERVAL = 1000

ALLOWED_SOURCE_TYPES = ("film_overview", "critics_consensus", "film_metadata")


# -----------------------------------------------------------------------------
# SQL queries
# -----------------------------------------------------------------------------

# Fetch all candidate documents — only the columns we need to plan/update.
SELECT_DOCS_SQL = text("""
    SELECT id, source_type, source_id, content_hash
    FROM rag_documents
    WHERE (CAST(:source_type_filter AS TEXT) IS NULL
           OR source_type = :source_type_filter)
    ORDER BY source_id, source_type
    LIMIT :limit
""")

# One-shot fetch of all films referenced by the current doc batch, with
# their joins flattened into the dict shape RAGImporter helpers expect.
# Genres come from the film_genres ↔ genres join (no denormalization
# column on films); cast_names/keyword_names/director are pre-hydrated
# (post-0.B.1) so we read them directly.
SELECT_FILMS_SQL = text("""
    SELECT
        f.tmdb_id,
        f.title,
        f.title_fr,
        f.overview,
        f.overview_fr,
        f.tagline,
        f.release_date,
        f.alternative_titles,
        f.director,
        f.cast_names,
        f.keyword_names,
        COALESCE(
            (SELECT array_agg(g.name ORDER BY g.name)
             FROM film_genres fg
             JOIN genres g ON g.id = fg.genre_id
             WHERE fg.film_id = f.id),
            '{}'::TEXT[]
        ) AS genres,
        rt.critics_consensus
    FROM films f
    LEFT JOIN rt_scores rt ON rt.film_id = f.id
    WHERE f.tmdb_id = ANY(:tmdb_ids)
""")


# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------


@dataclass
class RegenStats:
    """Aggregate counters for the regen run."""

    total_docs_scanned: int = 0
    docs_to_regenerate: int = 0
    docs_skipped_unchanged: int = 0
    docs_regenerated: int = 0
    docs_failed: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class DocRow:
    """Subset of `rag_documents` fields needed for planning."""

    doc_id: UUID
    source_type: str
    source_id: int
    content_hash: str | None


@dataclass
class Plan:
    """Per-document plan computed by `_compare_and_plan`."""

    doc_id: UUID
    tmdb_id: int
    source_type: str
    new_content: str
    new_hash: str
    needs_regen: bool


# -----------------------------------------------------------------------------
# Regenerator
# -----------------------------------------------------------------------------


class EmbeddingRegenerator:
    """Incremental embedding regeneration based on content_hash mismatch.

    Reconstructs `rag_documents.content` from current `horrorbot.films`
    state via the bilingual RAGImporter helpers (post-0.A.4) and
    regenerates embeddings only for docs whose MD5 changed.

    Attributes:
        embedding_service: Service producing 384-dim vectors.
        horrorbot_engine: Async engine bound to `horrorbot`.
        vectors_engine: Async engine bound to `horrorbot_vectors`.
        batch_size: Number of docs embedded + UPDATE-bulk-batched per round.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        horrorbot_engine: AsyncEngine,
        vectors_engine: AsyncEngine,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._embedding_service = embedding_service
        self._horrorbot_engine = horrorbot_engine
        self._vectors_engine = vectors_engine
        self._batch_size = batch_size

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def run(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        source_type_filter: str | None = None,
    ) -> RegenStats:
        """Execute the regeneration pipeline.

        Args:
            dry_run: When True, computes plans but skips embedding + UPDATE.
            limit: Max number of documents to scan.
            source_type_filter: Restrict to a single source_type.

        Returns:
            RegenStats with counters and timing.
        """
        started = datetime.now()
        stats = RegenStats()

        doc_rows = await self._fetch_all_doc_rows(limit, source_type_filter)
        stats.total_docs_scanned = len(doc_rows)
        logger.info("Scanned %d documents", stats.total_docs_scanned)

        if not doc_rows:
            stats.duration_seconds = (datetime.now() - started).total_seconds()
            return stats

        films_by_id = await self._fetch_films({d.source_id for d in doc_rows})
        plans = self._compare_and_plan(doc_rows, films_by_id, stats)

        if dry_run:
            logger.info(
                "Would regenerate: %d / %d",
                stats.docs_to_regenerate, stats.total_docs_scanned,
            )
        else:
            await self._apply_plans(plans, stats)

        stats.duration_seconds = (datetime.now() - started).total_seconds()
        return stats

    # -------------------------------------------------------------------------
    # Read helpers (DB)
    # -------------------------------------------------------------------------

    async def _fetch_all_doc_rows(
        self,
        limit: int | None,
        source_type_filter: str | None,
    ) -> list[DocRow]:
        """Load `rag_documents` rows we need to consider."""
        async with self._vectors_engine.connect() as conn:
            result = await conn.execute(
                SELECT_DOCS_SQL,
                {
                    "source_type_filter": source_type_filter,
                    "limit": limit if limit is not None else 10**9,
                },
            )
            return [
                DocRow(
                    doc_id=row.id,
                    source_type=row.source_type,
                    source_id=row.source_id,
                    content_hash=row.content_hash,
                )
                for row in result
            ]

    async def _fetch_films(self, tmdb_ids: set[int]) -> dict[int, dict[str, Any]]:
        """Load films for the given tmdb_ids, shaped for RAGImporter."""
        if not tmdb_ids:
            return {}
        async with self._horrorbot_engine.connect() as conn:
            result = await conn.execute(
                SELECT_FILMS_SQL, {"tmdb_ids": list(tmdb_ids)},
            )
            return {row.tmdb_id: _row_to_film_dict(row) for row in result}

    # -------------------------------------------------------------------------
    # Pure planning
    # -------------------------------------------------------------------------

    @staticmethod
    def _rebuild_document(film: dict[str, Any], source_type: str) -> str | None:
        """Rebuild a doc's content via the appropriate RAGImporter helper.

        Args:
            film: Film dict in RAGImporter shape.
            source_type: One of `film_overview`, `critics_consensus`, `film_metadata`.

        Returns:
            New content string, or None if the doc is now an orphan.
        """
        tmdb_id = film.get("tmdb_id", 0)
        if source_type == "film_overview":
            doc = RAGImporter._create_overview_doc(film, tmdb_id, {})
        elif source_type == "critics_consensus":
            doc = RAGImporter._create_consensus_doc(film, tmdb_id, {})
        elif source_type == "film_metadata":
            doc = RAGImporter._create_metadata_doc(film, tmdb_id, {})
        else:
            return None
        return doc.content if doc is not None else None

    @classmethod
    def _compare_and_plan(
        cls,
        doc_rows: list[DocRow],
        films_by_id: dict[int, dict[str, Any]],
        stats: RegenStats,
    ) -> list[Plan]:
        """Build per-doc Plans and update planning counters."""
        plans: list[Plan] = []
        for row in doc_rows:
            film = films_by_id.get(row.source_id)
            if film is None:
                logger.warning("Orphan doc: source_id=%d not in films", row.source_id)
                stats.docs_failed += 1
                stats.errors.append(f"orphan source_id={row.source_id}")
                continue
            new_content = cls._rebuild_document(film, row.source_type)
            if new_content is None:
                logger.warning(
                    "Doc %s: source_type=%s yields no content for tmdb_id=%d",
                    row.doc_id, row.source_type, row.source_id,
                )
                stats.docs_failed += 1
                continue
            new_hash = RAGImporter._compute_content_hash(new_content)
            needs_regen = row.content_hash != new_hash
            cls._bump_planning_counter(stats, needs_regen)
            plans.append(Plan(
                doc_id=row.doc_id, tmdb_id=row.source_id,
                source_type=row.source_type, new_content=new_content,
                new_hash=new_hash, needs_regen=needs_regen,
            ))
        return plans

    @staticmethod
    def _bump_planning_counter(stats: RegenStats, needs_regen: bool) -> None:
        if needs_regen:
            stats.docs_to_regenerate += 1
        else:
            stats.docs_skipped_unchanged += 1

    # -------------------------------------------------------------------------
    # Apply plans
    # -------------------------------------------------------------------------

    async def _apply_plans(self, plans: list[Plan], stats: RegenStats) -> None:
        """Embed + UPDATE every plan flagged needs_regen, batched."""
        targets = [p for p in plans if p.needs_regen]
        if not targets:
            return
        for batch in _chunked(targets, self._batch_size):
            try:
                await self._regen_one_batch(batch)
                stats.docs_regenerated += len(batch)
            except Exception as exc:  # noqa: BLE001
                stats.docs_failed += len(batch)
                stats.errors.append(str(exc))
                logger.exception("Batch failed (size=%d)", len(batch))
            self._maybe_log_progress(stats)

    async def _regen_one_batch(self, batch: list[Plan]) -> None:
        """Embed `batch` then bulk-UPDATE rag_documents."""
        contents = [p.new_content for p in batch]
        embeddings = self._embedding_service.generate_batch(contents)
        rows = [
            {
                "id": str(p.doc_id),
                "content": p.new_content,
                "embedding": str(emb),
                "hash": p.new_hash,
            }
            for p, emb in zip(batch, embeddings, strict=True)
        ]
        await self._bulk_update(rows)

    async def _bulk_update(self, rows: list[dict[str, Any]]) -> None:
        """Single-round-trip UPDATE ... FROM (VALUES ...) for the batch."""
        if not rows:
            return
        placeholders = []
        params: dict[str, Any] = {}
        for i, row in enumerate(rows):
            placeholders.append(
                f"(CAST(:id_{i} AS UUID), :content_{i}, "
                f"CAST(:embedding_{i} AS vector), :hash_{i})",
            )
            params[f"id_{i}"] = row["id"]
            params[f"content_{i}"] = row["content"]
            params[f"embedding_{i}"] = row["embedding"]
            params[f"hash_{i}"] = row["hash"]

        stmt = text(f"""
            UPDATE rag_documents r
            SET content = u.content,
                embedding = u.embedding,
                content_hash = u.content_hash,
                updated_at = NOW()
            FROM (VALUES {", ".join(placeholders)})
                AS u(id, content, embedding, content_hash)
            WHERE r.id = u.id
        """)
        async with self._vectors_engine.begin() as conn:
            await conn.execute(stmt, params)

    @staticmethod
    def _maybe_log_progress(stats: RegenStats) -> None:
        if stats.docs_regenerated and stats.docs_regenerated % LOG_INTERVAL == 0:
            logger.info(
                "Progress: regenerated=%d failed=%d",
                stats.docs_regenerated, stats.docs_failed,
            )


# -----------------------------------------------------------------------------
# Pure helpers
# -----------------------------------------------------------------------------


def _row_to_film_dict(row: Any) -> dict[str, Any]:
    """Map a SELECT_FILMS_SQL row into the dict shape RAGImporter expects."""
    return {
        "tmdb_id": row.tmdb_id,
        "title": row.title,
        "title_fr": row.title_fr,
        "overview": row.overview,
        "overview_fr": row.overview_fr,
        "tagline": row.tagline,
        "release_date": row.release_date.isoformat() if row.release_date else None,
        "alternative_titles": list(row.alternative_titles or []),
        "director": row.director,
        "cast": list(row.cast_names or []),
        "keywords": list(row.keyword_names or []),
        "genres": list(row.genres or []),
        "critics_consensus": row.critics_consensus,
    }


def _chunked(items: list[Plan], size: int) -> Iterable[list[Plan]]:
    """Yield successive `size`-chunks of `items`."""
    for start in range(0, len(items), size):
        yield items[start:start + size]


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--source-type", choices=ALLOWED_SOURCE_TYPES, default=None,
    )
    return parser.parse_args(argv)


async def _run_cli(args: argparse.Namespace) -> RegenStats:
    horrorbot_engine = create_async_engine(
        settings.database.async_url, pool_pre_ping=True,
    )
    vectors_engine = create_async_engine(
        settings.database.vectors_async_url, pool_pre_ping=True,
    )
    try:
        regen = EmbeddingRegenerator(
            embedding_service=get_embedding_service(),
            horrorbot_engine=horrorbot_engine,
            vectors_engine=vectors_engine,
            batch_size=args.batch_size,
        )
        return await regen.run(
            dry_run=args.dry_run,
            limit=args.limit,
            source_type_filter=args.source_type,
        )
    finally:
        await horrorbot_engine.dispose()
        await vectors_engine.dispose()


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    args = _parse_args(argv)
    stats = asyncio.run(_run_cli(args))
    logger.info("Final stats: %s", stats)


if __name__ == "__main__":
    main()
