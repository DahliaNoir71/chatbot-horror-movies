"""One-shot backfill migration for the multilingual dataset (2026-04-16).

Two-stage backfill bringing the existing 63K films corpus up to the post-0.A.3
schema:

1. **Stage A — SQL hydration** (seconds) : populate `director`, `cast_names` and
   `keyword_names` from the `credits` / `film_keywords` relations. The
   PostgreSQL trigger installed in `05_search_vectors.sql` recomputes both
   `search_vector_{fr,en}` automatically on the touched rows.

2. **Stage B — TMDB enrichment** (~30 min) : for every film with `title_fr IS
   NULL`, fetch `translations` + `alternative_titles` via `get_movie_full`
   (single HTTP call, see 0.A.3) and UPDATE the three FR columns. Idempotent
   and checkpointed — safe to resume after a crash.

Invocation:

    python -m scripts.migrations.backfill_multilingual_20260416 --stage all
    python -m scripts.migrations.backfill_multilingual_20260416 --stage a --dry-run
    python -m scripts.migrations.backfill_multilingual_20260416 --stage b --limit 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.etl.extractors.tmdb.client import TMDBClient, TMDBNotFoundError
from src.etl.extractors.tmdb.normalizer import TMDBNormalizer
from src.settings import settings

logger = logging.getLogger("scripts.migrations.backfill_multilingual")

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

DEFAULT_BATCH_SIZE = 100
CHECKPOINT_INTERVAL = 1000
LOG_INTERVAL = 1000
RATE_LIMIT_MARGIN = 5  # leave headroom vs the TMDB 40/10s cap

CHECKPOINT_PATH = (
    Path(__file__).parent / ".backfill_multilingual_checkpoint.json"
)

# SQL constants — pulled out to keep methods short and to expose them for
# unit testing.
STAGE_A_SQL = text("""
    UPDATE films f SET
        director = sub.director_name,
        cast_names = sub.cast_array,
        keyword_names = sub.kw_array
    FROM (
        SELECT f.id,
            (SELECT c.person_name::TEXT FROM credits c
             WHERE c.film_id = f.id AND c.role_type = 'director'
             ORDER BY c.display_order LIMIT 1) AS director_name,
            COALESCE(
                ARRAY(
                    SELECT c.person_name::TEXT FROM credits c
                    WHERE c.film_id = f.id AND c.role_type = 'actor'
                    ORDER BY c.display_order
                    LIMIT 10
                ),
                '{}'::TEXT[]
            ) AS cast_array,
            COALESCE(
                (SELECT array_agg(k.name::TEXT ORDER BY k.name)
                 FROM film_keywords fk
                 JOIN keywords k ON k.id = fk.keyword_id
                 WHERE fk.film_id = f.id),
                '{}'::TEXT[]
            ) AS kw_array
        FROM films f
    ) sub
    WHERE f.id = sub.id
      AND (
        f.director IS DISTINCT FROM sub.director_name
        OR f.cast_names IS DISTINCT FROM sub.cast_array
        OR f.keyword_names IS DISTINCT FROM sub.kw_array
      )
""")

SELECT_UNENRICHED_SQL = text("""
    SELECT tmdb_id FROM films
    WHERE title_fr IS NULL
      AND (CAST(:resume_from AS INTEGER) IS NULL OR tmdb_id > :resume_from)
    ORDER BY tmdb_id
    LIMIT :limit
""")

UPDATE_TRANSLATIONS_SQL = text("""
    UPDATE films SET
        title_fr = :title_fr,
        overview_fr = :overview_fr,
        alternative_titles = :alternative_titles
    WHERE tmdb_id = :tmdb_id
""")


# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------


@dataclass
class BackfillStats:
    """Aggregate counters for the backfill run."""

    stage_a_updated: int = 0
    stage_b_seen: int = 0
    stage_b_updated: int = 0
    stage_b_skipped_404: int = 0
    stage_b_errors: int = 0


@dataclass
class EnrichmentResult:
    """Outcome of a single TMDB fetch for one film."""

    tmdb_id: int
    title_fr: str | None = None
    overview_fr: str | None = None
    alternative_titles: list[str] = field(default_factory=list)
    not_found: bool = False
    error: str | None = None


# Type alias for the injected TMDB call — simplifies mocking in tests.
TMDBFetchFn = Callable[[int], Awaitable[EnrichmentResult]]


# -----------------------------------------------------------------------------
# Backfiller
# -----------------------------------------------------------------------------


class MultilingualBackfiller:
    """Two-stage backfill for the existing films dataset.

    Attributes:
        engine: Async engine bound to the `horrorbot` database.
        tmdb_fetch: Awaitable that returns an EnrichmentResult for a tmdb_id.
        checkpoint_path: Path for resume-after-crash bookkeeping.
        batch_size: Number of films fetched in parallel per batch.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        tmdb_fetch: TMDBFetchFn,
        checkpoint_path: Path = CHECKPOINT_PATH,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._engine = engine
        self._tmdb_fetch = tmdb_fetch
        self._checkpoint_path = checkpoint_path
        self._batch_size = batch_size

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def run(
        self,
        stage: str = "all",
        dry_run: bool = False,
        limit: int | None = None,
    ) -> BackfillStats:
        """Execute the requested stage(s) and return aggregated stats.

        Args:
            stage: One of 'a', 'b', or 'all'.
            dry_run: When True, rollback all writes.
            limit: Optional film count cap for Stage B.

        Returns:
            BackfillStats with per-stage counters.
        """
        stats = BackfillStats()
        if stage in ("a", "all"):
            stats.stage_a_updated = await self._stage_a_hydrate(dry_run)
        if stage in ("b", "all"):
            await self._stage_b_enrich(stats, dry_run, limit)
        return stats

    # -------------------------------------------------------------------------
    # Stage A — SQL hydration
    # -------------------------------------------------------------------------

    async def _stage_a_hydrate(self, dry_run: bool) -> int:
        """Hydrate denormalized fields via a single bulk UPDATE.

        Args:
            dry_run: When True, rollback after execution.

        Returns:
            Number of film rows updated.
        """
        logger.info("Stage A: hydrating denormalized fields")
        async with self._engine.begin() as conn:
            result = await conn.execute(STAGE_A_SQL)
            count = result.rowcount or 0
            if dry_run:
                await conn.rollback()
                logger.info("Stage A [dry-run]: %d films would be updated", count)
            else:
                logger.info("Hydrated denormalized fields for %d films", count)
        return count

    # -------------------------------------------------------------------------
    # Stage B — TMDB enrichment
    # -------------------------------------------------------------------------

    async def _stage_b_enrich(
        self,
        stats: BackfillStats,
        dry_run: bool,
        limit: int | None,
    ) -> None:
        """Fetch + UPDATE French translations for all remaining films.

        Args:
            stats: Counters updated in place.
            dry_run: When True, rollback after each batch.
            limit: Optional cap on number of films processed.
        """
        resume_from = self._load_checkpoint()
        if resume_from is not None:
            logger.info("Stage B: resuming after tmdb_id=%d", resume_from)

        remaining = limit
        while True:
            batch_limit = self._next_batch_limit(remaining)
            if batch_limit == 0:
                break
            ids = await self._fetch_unenriched_ids(resume_from, batch_limit)
            if not ids:
                break

            await self._process_batch(ids, stats, dry_run)
            resume_from = ids[-1]
            if remaining is not None:
                remaining -= len(ids)
            self._maybe_checkpoint(stats.stage_b_seen, resume_from)

        self._clear_checkpoint()

    def _next_batch_limit(self, remaining: int | None) -> int:
        """Compute next batch SQL LIMIT from remaining cap."""
        if remaining is None:
            return self._batch_size
        return min(self._batch_size, max(remaining, 0))

    async def _fetch_unenriched_ids(
        self,
        resume_from: int | None,
        batch_limit: int,
    ) -> list[int]:
        """Return the next batch of tmdb_ids lacking French enrichment."""
        async with self._engine.connect() as conn:
            rows = await conn.execute(
                SELECT_UNENRICHED_SQL,
                {"resume_from": resume_from, "limit": batch_limit},
            )
            return [row[0] for row in rows]

    async def _process_batch(
        self,
        tmdb_ids: list[int],
        stats: BackfillStats,
        dry_run: bool,
    ) -> None:
        """Fetch translations in parallel then bulk-UPDATE the batch."""
        results = await asyncio.gather(
            *(self._tmdb_fetch(tid) for tid in tmdb_ids),
            return_exceptions=False,
        )
        await self._apply_batch_updates(results, stats, dry_run)
        self._log_progress(stats)

    async def _apply_batch_updates(
        self,
        results: Iterable[EnrichmentResult],
        stats: BackfillStats,
        dry_run: bool,
    ) -> None:
        """Apply UPDATEs and bump per-outcome counters."""
        rows_to_update: list[dict[str, Any]] = []
        for result in results:
            stats.stage_b_seen += 1
            if result.not_found:
                stats.stage_b_skipped_404 += 1
                continue
            if result.error is not None:
                stats.stage_b_errors += 1
                continue
            rows_to_update.append(self._build_update_row(result))

        if not rows_to_update:
            return

        async with self._engine.begin() as conn:
            await conn.execute(UPDATE_TRANSLATIONS_SQL, rows_to_update)
            if dry_run:
                await conn.rollback()
            else:
                stats.stage_b_updated += len(rows_to_update)

    @staticmethod
    def _build_update_row(result: EnrichmentResult) -> dict[str, Any]:
        """Shape one EnrichmentResult into a parameters dict for UPDATE."""
        return {
            "tmdb_id": result.tmdb_id,
            "title_fr": result.title_fr,
            "overview_fr": result.overview_fr,
            "alternative_titles": result.alternative_titles,
        }

    def _log_progress(self, stats: BackfillStats) -> None:
        """Emit a progress line every LOG_INTERVAL films."""
        if stats.stage_b_seen % LOG_INTERVAL == 0 and stats.stage_b_seen:
            logger.info(
                "Stage B progress: seen=%d updated=%d 404=%d errors=%d",
                stats.stage_b_seen,
                stats.stage_b_updated,
                stats.stage_b_skipped_404,
                stats.stage_b_errors,
            )

    # -------------------------------------------------------------------------
    # Checkpoint
    # -------------------------------------------------------------------------

    def _load_checkpoint(self) -> int | None:
        """Return the last processed tmdb_id, or None if no checkpoint."""
        if not self._checkpoint_path.exists():
            return None
        try:
            data = json.loads(self._checkpoint_path.read_text(encoding="utf-8"))
            return int(data["last_tmdb_id_processed"])
        except (KeyError, ValueError) as exc:
            logger.warning("Corrupt checkpoint ignored: %s", exc)
            return None

    def _maybe_checkpoint(self, seen: int, last_tmdb_id: int) -> None:
        """Persist the checkpoint every CHECKPOINT_INTERVAL films."""
        if seen == 0 or seen % CHECKPOINT_INTERVAL != 0:
            return
        self._checkpoint_path.write_text(
            json.dumps({"last_tmdb_id_processed": last_tmdb_id}),
            encoding="utf-8",
        )

    def _clear_checkpoint(self) -> None:
        """Remove the checkpoint file when the stage completes cleanly."""
        if self._checkpoint_path.exists():
            self._checkpoint_path.unlink()


# -----------------------------------------------------------------------------
# Real TMDB fetcher
# -----------------------------------------------------------------------------


def _make_real_tmdb_fetcher() -> tuple[TMDBFetchFn, Callable[[], None]]:
    """Build the production TMDB fetch function.

    Wraps the sync TMDBClient in asyncio.to_thread() with a Semaphore capped
    at `requests_per_period - RATE_LIMIT_MARGIN` so we stay under the 40/10s
    TMDB limit even under worst-case worker scheduling.

    Returns:
        (fetcher, shutdown) — call shutdown() when done.
    """
    client_ctx = TMDBClient()
    client = client_ctx.__enter__()
    semaphore = asyncio.Semaphore(
        max(1, settings.tmdb.requests_per_period - RATE_LIMIT_MARGIN),
    )

    async def fetch(tmdb_id: int) -> EnrichmentResult:
        async with semaphore:
            try:
                raw = await asyncio.to_thread(client.get_movie_full, tmdb_id)
            except TMDBNotFoundError:
                logger.warning("tmdb_id=%d not found (404)", tmdb_id)
                return EnrichmentResult(tmdb_id=tmdb_id, not_found=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("tmdb_id=%d enrichment failed: %s", tmdb_id, exc)
                return EnrichmentResult(tmdb_id=tmdb_id, error=str(exc))

        return EnrichmentResult(
            tmdb_id=tmdb_id,
            title_fr=TMDBNormalizer._extract_french_title(raw.get("translations")),
            overview_fr=TMDBNormalizer._extract_french_overview(raw.get("translations")),
            alternative_titles=TMDBNormalizer._extract_alternative_titles(
                raw.get("alternative_titles"),
            ),
        )

    def shutdown() -> None:
        client_ctx.__exit__(None, None, None)

    return fetch, shutdown


# -----------------------------------------------------------------------------
# CLI entry point
# -----------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["a", "b", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    return parser.parse_args(argv)


async def _run_cli(args: argparse.Namespace) -> BackfillStats:
    engine = create_async_engine(settings.database.async_url, pool_pre_ping=True)
    fetcher, shutdown = _make_real_tmdb_fetcher()
    try:
        backfiller = MultilingualBackfiller(
            engine=engine,
            tmdb_fetch=fetcher,
            batch_size=args.batch_size,
        )
        return await backfiller.run(
            stage=args.stage, dry_run=args.dry_run, limit=args.limit,
        )
    finally:
        shutdown()
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = _parse_args(argv)
    stats = asyncio.run(_run_cli(args))
    logger.info("Final stats: %s", stats)


if __name__ == "__main__":
    main()
