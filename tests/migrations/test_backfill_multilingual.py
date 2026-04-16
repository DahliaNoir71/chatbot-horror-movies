"""Unit tests for the multilingual backfill migration.

Runs against `horrorbot_migration_test` (provisioned by `conftest.py`),
a dedicated empty Postgres database with the same schema as the live
`horrorbot` DB. TMDB is mocked through the injected fetch callable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from scripts.migrations.backfill_multilingual_20260416 import (
    CHECKPOINT_PATH,
    EnrichmentResult,
    MultilingualBackfiller,
)
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


async def _insert_film(engine: AsyncEngine, **fields: object) -> int:
    """Insert a film row, return its surrogate id."""
    cols = ", ".join(fields.keys())
    placeholders = ", ".join(f":{k}" for k in fields)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO films ({cols}) VALUES ({placeholders})"),
            fields,
        )
        return (
            await conn.execute(
                text("SELECT id FROM films WHERE tmdb_id = :tid"),
                {"tid": fields["tmdb_id"]},
            )
        ).scalar_one()


async def _insert_credit(engine: AsyncEngine, **fields: object) -> None:
    cols = ", ".join(fields.keys())
    placeholders = ", ".join(f":{k}" for k in fields)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO credits ({cols}) VALUES ({placeholders})"),
            fields,
        )


async def _select_one(engine: AsyncEngine, query: str, **params: object) -> object:
    async with engine.connect() as conn:
        return (await conn.execute(text(query), params)).scalar_one()


async def _unused_fetch(tmdb_id: int) -> EnrichmentResult:
    raise AssertionError(f"TMDB fetch should not be called (tmdb_id={tmdb_id})")


@pytest.fixture
def tmp_checkpoint(tmp_path: Path) -> Path:
    """Isolated checkpoint path so tests don't touch the production one."""
    return tmp_path / ".backfill_checkpoint.json"


# -----------------------------------------------------------------------------
# Stage A — SQL hydration
# -----------------------------------------------------------------------------


async def test_stage_a_hydrate_idempotent(
    clean_migration_db: AsyncEngine, tmp_checkpoint: Path,
) -> None:
    """Second run on an already-hydrated film performs zero updates."""
    film_id = await _insert_film(clean_migration_db, tmdb_id=1, title="Test")
    await _insert_credit(
        clean_migration_db,
        film_id=film_id, tmdb_person_id=1, person_name="Director X",
        role_type="director", display_order=0,
    )

    backfiller = MultilingualBackfiller(
        engine=clean_migration_db, tmdb_fetch=_unused_fetch,
        checkpoint_path=tmp_checkpoint,
    )
    stats1 = await backfiller.run(stage="a")
    stats2 = await backfiller.run(stage="a")

    assert stats1.stage_a_updated == 1
    assert stats2.stage_a_updated == 0

    director = await _select_one(
        clean_migration_db, "SELECT director FROM films WHERE tmdb_id = 1",
    )
    assert director == "Director X"


async def test_stage_a_top_10_cast(
    clean_migration_db: AsyncEngine, tmp_checkpoint: Path,
) -> None:
    """Film with 20 actors → cast_names truncated to 10 by display_order."""
    film_id = await _insert_film(clean_migration_db, tmdb_id=2, title="Cast20")
    for i in range(20):
        await _insert_credit(
            clean_migration_db,
            film_id=film_id, tmdb_person_id=1000 + i,
            person_name=f"Actor{i:02d}", role_type="actor", display_order=i,
        )

    backfiller = MultilingualBackfiller(
        engine=clean_migration_db, tmdb_fetch=_unused_fetch,
        checkpoint_path=tmp_checkpoint,
    )
    await backfiller.run(stage="a")

    cast_names = await _select_one(
        clean_migration_db, "SELECT cast_names FROM films WHERE tmdb_id = 2",
    )
    assert len(cast_names) == 10
    assert cast_names[0] == "Actor00"
    assert cast_names[9] == "Actor09"


# -----------------------------------------------------------------------------
# Stage B — TMDB enrichment
# -----------------------------------------------------------------------------


async def test_stage_b_skip_already_enriched(
    clean_migration_db: AsyncEngine, tmp_checkpoint: Path,
) -> None:
    """Films with title_fr already set must not trigger TMDB fetch."""
    await _insert_film(
        clean_migration_db, tmdb_id=3, title="Already", title_fr="Déjà",
    )

    backfiller = MultilingualBackfiller(
        engine=clean_migration_db, tmdb_fetch=_unused_fetch,
        checkpoint_path=tmp_checkpoint, batch_size=5,
    )
    stats = await backfiller.run(stage="b")

    assert stats.stage_b_seen == 0
    assert stats.stage_b_updated == 0


async def test_stage_b_skip_on_404(
    clean_migration_db: AsyncEngine, tmp_checkpoint: Path,
) -> None:
    """404 from TMDB logs a warning and continues without crashing."""
    await _insert_film(clean_migration_db, tmdb_id=4, title="Missing")

    async def fetch(tmdb_id: int) -> EnrichmentResult:
        return EnrichmentResult(tmdb_id=tmdb_id, not_found=True)

    backfiller = MultilingualBackfiller(
        engine=clean_migration_db, tmdb_fetch=fetch,
        checkpoint_path=tmp_checkpoint, batch_size=5,
    )
    stats = await backfiller.run(stage="b")

    assert stats.stage_b_seen == 1
    assert stats.stage_b_skipped_404 == 1
    assert stats.stage_b_updated == 0
    title_fr = await _select_one(
        clean_migration_db, "SELECT title_fr FROM films WHERE tmdb_id = 4",
    )
    assert title_fr is None


async def test_stage_b_dry_run_no_writes(
    clean_migration_db: AsyncEngine, tmp_checkpoint: Path,
) -> None:
    """Dry-run Stage B fetches but rolls back every UPDATE."""
    await _insert_film(clean_migration_db, tmdb_id=5, title="Dry")

    async def fetch(tmdb_id: int) -> EnrichmentResult:
        return EnrichmentResult(
            tmdb_id=tmdb_id,
            title_fr="Titre Sec", overview_fr="Synopsis FR",
            alternative_titles=["Alt"],
        )

    backfiller = MultilingualBackfiller(
        engine=clean_migration_db, tmdb_fetch=fetch,
        checkpoint_path=tmp_checkpoint, batch_size=5,
    )
    stats = await backfiller.run(stage="b", dry_run=True)

    assert stats.stage_b_seen == 1
    assert stats.stage_b_updated == 0
    title_fr = await _select_one(
        clean_migration_db, "SELECT title_fr FROM films WHERE tmdb_id = 5",
    )
    assert title_fr is None


async def test_resume_from_checkpoint(
    clean_migration_db: AsyncEngine, tmp_checkpoint: Path,
) -> None:
    """Checkpoint makes Stage B skip already-processed tmdb_ids on resume."""
    await _insert_film(clean_migration_db, tmdb_id=10, title="First")
    await _insert_film(clean_migration_db, tmdb_id=11, title="Second")

    tmp_checkpoint.write_text(
        json.dumps({"last_tmdb_id_processed": 10}),
        encoding="utf-8",
    )

    fetched: list[int] = []

    async def fetch(tmdb_id: int) -> EnrichmentResult:
        fetched.append(tmdb_id)
        return EnrichmentResult(
            tmdb_id=tmdb_id, title_fr=f"FR{tmdb_id}",
            overview_fr=None, alternative_titles=[],
        )

    backfiller = MultilingualBackfiller(
        engine=clean_migration_db, tmdb_fetch=fetch,
        checkpoint_path=tmp_checkpoint, batch_size=5,
    )
    await backfiller.run(stage="b")

    assert fetched == [11]
    assert not tmp_checkpoint.exists()


# -----------------------------------------------------------------------------
# Sanity check
# -----------------------------------------------------------------------------


def test_production_checkpoint_location() -> None:
    """Production checkpoint sits alongside the migration script."""
    assert CHECKPOINT_PATH.name == ".backfill_multilingual_checkpoint.json"
    assert CHECKPOINT_PATH.parent.name == "migrations"
