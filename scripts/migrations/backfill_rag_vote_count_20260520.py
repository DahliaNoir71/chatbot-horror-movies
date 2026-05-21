"""One-shot backfill: copy films.vote_count into rag_documents.vote_count (2026-05-20).

`vote_count` lives in the `horrorbot` database (films table); the RAG documents
live in `horrorbot_vectors`. The retrieval popularity floor introduced by
`docker/init-db/08_rag_vote_count.sql` needs the value local to `rag_documents`,
so this script copies it across, joining on the shared logical key
`rag_documents.source_id = films.tmdb_id`.

Run once after `08_rag_vote_count.sql`, and again after any ETL load that adds
films. Idempotent — rerunning simply rewrites the same values.

Invocation:

    python -m scripts.migrations.backfill_rag_vote_count_20260520
    python -m scripts.migrations.backfill_rag_vote_count_20260520 --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import create_engine, text

from src.settings import settings

logger = logging.getLogger("scripts.migrations.backfill_rag_vote_count")

# Popularity floor used by search_similar_documents — kept here only to report
# how many documents will be retrievable once the backfill lands.
_NOTABLE_THRESHOLD = 100

_SELECT_VOTES_SQL = text("SELECT tmdb_id, vote_count FROM films")

# Staged in a TEMP table (ON COMMIT DROP) so the cross-database copy lands as a
# single set-based UPDATE instead of tens of thousands of round-trips.
_CREATE_TMP_SQL = text("""
    CREATE TEMP TABLE _vote_backfill (
        tmdb_id INTEGER PRIMARY KEY,
        vote_count INTEGER NOT NULL
    ) ON COMMIT DROP
""")
_INSERT_TMP_SQL = text(
    "INSERT INTO _vote_backfill (tmdb_id, vote_count) VALUES (:tmdb_id, :vote_count)"
)
_UPDATE_SQL = text("""
    UPDATE rag_documents d
    SET vote_count = b.vote_count
    FROM _vote_backfill b
    WHERE d.source_id = b.tmdb_id
""")
_COUNT_NOTABLE_SQL = text("SELECT count(*) FROM rag_documents WHERE vote_count >= :threshold")


def _read_film_votes() -> list[dict[str, int]]:
    """Read (tmdb_id, vote_count) for every film from the horrorbot database.

    Returns:
        One mapping per film, with a NULL vote_count coerced to 0.
    """
    engine = create_engine(settings.database.sync_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(_SELECT_VOTES_SQL)
            return [
                {"tmdb_id": row.tmdb_id, "vote_count": int(row.vote_count or 0)} for row in rows
            ]
    finally:
        engine.dispose()


def _apply_backfill(votes: list[dict[str, int]]) -> tuple[int, int]:
    """Copy vote counts into rag_documents via a temp-table join.

    Args:
        votes: Mappings of {"tmdb_id", "vote_count"} from `_read_film_votes`.

    Returns:
        (rows_updated, notable_docs) — documents touched, and documents that
        now clear the `_NOTABLE_THRESHOLD` popularity floor.
    """
    engine = create_engine(settings.database.vectors_sync_url)
    try:
        with engine.begin() as conn:
            conn.execute(_CREATE_TMP_SQL)
            conn.execute(_INSERT_TMP_SQL, votes)
            updated = conn.execute(_UPDATE_SQL).rowcount
            notable = conn.execute(
                _COUNT_NOTABLE_SQL, {"threshold": _NOTABLE_THRESHOLD}
            ).scalar_one()
        return updated, int(notable)
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
        help="Read and report film counts without writing to rag_documents",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = _parse_args(argv)

    votes = _read_film_votes()
    notable_films = sum(1 for v in votes if v["vote_count"] >= _NOTABLE_THRESHOLD)
    logger.info(
        "Read %d films (%d with vote_count >= %d)",
        len(votes),
        notable_films,
        _NOTABLE_THRESHOLD,
    )

    if args.dry_run:
        logger.info("Dry run — rag_documents left unchanged")
        return

    updated, notable_docs = _apply_backfill(votes)
    logger.info(
        "Backfill complete: %d rag_documents updated, %d now retrievable (vote_count >= %d)",
        updated,
        notable_docs,
        _NOTABLE_THRESHOLD,
    )


if __name__ == "__main__":
    main()
