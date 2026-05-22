"""One-shot purge: drop short-film documents from rag_documents (2026-05-22).

The chatbot recommends feature films. Short films (runtime below the
standard 40-minute short/feature boundary) — e.g. the 2003 Saw
proof-of-concept — pollute retrieval and surface beside their
feature-length namesakes as apparent duplicates. `rag_importer` now
skips them at import time; this script removes the ones already indexed.

`runtime` lives in the `horrorbot` database (films table); the RAG
documents live in `horrorbot_vectors`, joined on the shared logical key
`rag_documents.source_id = films.tmdb_id`. A NULL or 0 runtime is treated
as unknown — the film is kept, since the data (not the film) is missing.

Idempotent — rerunning deletes nothing once the corpus is clean.

Invocation:

    python -m scripts.migrations.purge_short_films_20260522
    python -m scripts.migrations.purge_short_films_20260522 --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import create_engine, text

from src.settings import settings

logger = logging.getLogger("scripts.migrations.purge_short_films")

# Standard short/feature boundary in minutes — mirrors rag_importer's
# MIN_FEATURE_RUNTIME. A film at or above this is a feature.
_MIN_FEATURE_RUNTIME = 40

_SELECT_SHORTS_SQL = text(
    "SELECT tmdb_id FROM films WHERE runtime > 0 AND runtime < :min_runtime"
)
_DELETE_DOCS_SQL = text("DELETE FROM rag_documents WHERE source_id = ANY(:ids)")


def _read_short_film_ids() -> list[int]:
    """Read the tmdb_id of every short film from the horrorbot database.

    Returns:
        TMDB ids of films whose runtime is known and below the boundary.
    """
    engine = create_engine(settings.database.sync_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(_SELECT_SHORTS_SQL, {"min_runtime": _MIN_FEATURE_RUNTIME})
            return [row.tmdb_id for row in rows]
    finally:
        engine.dispose()


def _purge_documents(short_ids: list[int]) -> int:
    """Delete every rag_documents row whose source film is a short.

    Args:
        short_ids: TMDB ids of short films from `_read_short_film_ids`.

    Returns:
        Number of rag_documents rows deleted.
    """
    if not short_ids:
        return 0
    engine = create_engine(settings.database.vectors_sync_url)
    try:
        with engine.begin() as conn:
            return conn.execute(_DELETE_DOCS_SQL, {"ids": short_ids}).rowcount
    finally:
        engine.dispose()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many short films were found without deleting any document",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = _parse_args(argv)

    short_ids = _read_short_film_ids()
    logger.info("Found %d short films (runtime < %d min)", len(short_ids), _MIN_FEATURE_RUNTIME)

    if args.dry_run:
        logger.info("Dry run — rag_documents left unchanged")
        return

    deleted = _purge_documents(short_ids)
    logger.info("Purge complete: %d rag_documents deleted", deleted)


if __name__ == "__main__":
    main()
