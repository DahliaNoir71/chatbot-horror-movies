"""Fixtures for migration script tests.

Provisions a dedicated empty test database (`horrorbot_migration_test`)
applying the horrorbot schema + the 05_search_vectors trigger, so the
backfiller's SQL can run without polluting the 63K-film live corpus.

Function-scoped: each test gets a fresh DB. Setup ~500ms.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from tests.etl.conftest import _load_real_env

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

TEST_DB_NAME = "horrorbot_migration_test"
_INIT_DB_DIR = Path(__file__).resolve().parents[2] / "docker" / "init-db"


def _resolve_pg_env() -> dict[str, str] | None:
    """Build a complete POSTGRES_* env dict, preferring `.env` over shell."""
    shell = {k: v for k, v in os.environ.items() if v}
    env = shell | _load_real_env()
    required = (
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD",
    )
    if not all(env.get(k) for k in required):
        return None
    return env


def _admin_dsn(env: dict[str, str]) -> str:
    """asyncpg DSN to the admin `postgres` database."""
    return (
        f"postgres://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
        f"@{env['POSTGRES_HOST']}:{env['POSTGRES_PORT']}/postgres"
    )


def _test_dsn(env: dict[str, str]) -> str:
    """asyncpg DSN to the dedicated test database."""
    return (
        f"postgres://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
        f"@{env['POSTGRES_HOST']}:{env['POSTGRES_PORT']}/{TEST_DB_NAME}"
    )


def _test_async_url(env: dict[str, str]) -> str:
    """SQLAlchemy URL for the dedicated test DB."""
    return (
        f"postgresql+asyncpg://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
        f"@{env['POSTGRES_HOST']}:{env['POSTGRES_PORT']}/{TEST_DB_NAME}"
    )


def _strip_psql_metacommands(sql: str) -> str:
    """Remove psql-only directives (\\connect, \\echo, etc.)."""
    return "\n".join(
        line for line in sql.splitlines()
        if not line.strip().startswith("\\")
    )


def _drop_vectors_section(sql: str) -> str:
    """Strip the `\\connect horrorbot_vectors` block from 05_search_vectors.sql.

    The test DB has only the relational schema; the rag_documents table
    (and the content_hash column) lives in `horrorbot_vectors`, which is
    out of scope for backfill tests.
    """
    lines = sql.splitlines()
    kept: list[str] = []
    inside_vectors = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("\\connect horrorbot_vectors"):
            inside_vectors = True
            continue
        if stripped.startswith("\\connect horrorbot"):
            inside_vectors = False
            continue
        if not inside_vectors:
            kept.append(line)
    return "\n".join(kept)


async def _admin_drop(dsn: str) -> None:
    admin = await asyncpg.connect(dsn)
    try:
        await admin.execute(
            f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)',
        )
    finally:
        await admin.close()


async def _admin_create(dsn: str) -> None:
    admin = await asyncpg.connect(dsn)
    try:
        await admin.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await admin.close()


async def _apply_schema(dsn: str) -> None:
    """Load horrorbot schema + 05_search_vectors trigger into the test DB."""
    schema_sql = (_INIT_DB_DIR / "02_horrorbot_schema.sql").read_text(encoding="utf-8")
    search_sql = (_INIT_DB_DIR / "05_search_vectors.sql").read_text(encoding="utf-8")

    conn = await asyncpg.connect(dsn)
    try:
        # uuid-ossp is required by `etl_runs.run_id` default in 02_horrorbot_schema
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        await conn.execute(_strip_psql_metacommands(schema_sql))
        await conn.execute(
            _strip_psql_metacommands(_drop_vectors_section(search_sql)),
        )
    finally:
        await conn.close()


@pytest.fixture
async def clean_migration_db() -> AsyncGenerator[AsyncEngine, None]:
    """Per-test fresh `horrorbot_migration_test` DB (created + dropped each call)."""
    env = _resolve_pg_env()
    if env is None:
        pytest.skip("POSTGRES_* not configured for migration tests")

    admin_dsn = _admin_dsn(env)
    try:
        await _admin_drop(admin_dsn)
        await _admin_create(admin_dsn)
        await _apply_schema(_test_dsn(env))
    except Exception as exc:  # noqa: BLE001
        await _admin_drop(admin_dsn)
        pytest.skip(f"Cannot provision test DB: {exc}")

    engine = create_async_engine(_test_async_url(env), pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()
        await _admin_drop(admin_dsn)
