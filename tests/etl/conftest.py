"""Shared fixtures for ETL integration tests.

Provides a real asyncpg connection to the running Docker `horrorbot`
database for trigger-level tests, and a TMDBExtractor wired to a real
API key for end-to-end extraction tests.

Both fixtures auto-skip when their prerequisites (docker compose up,
real TMDB key exported in the shell) are not met, so the suite stays
green in CI without infrastructure.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

# Synthetic tmdb_ids reserved for fresh-install integration tests.
# Chosen well above any real TMDB id likely to appear in the corpus
# so pre/post cleanup DELETEs never touch ingested data.
TEST_TMDB_IDS: tuple[int, ...] = (99001, 99002, 99003)

# Placeholder value used by .env.test — real extraction tests skip when
# settings.tmdb.api_key resolves to this.
_TMDB_PLACEHOLDER_KEY = "test-api-key"


def _load_real_env() -> dict[str, str]:
    """Read the real `.env` (docker compose vars) without mutating os.environ.

    pytest-dotenv loads `.env.test` first — its placeholder POSTGRES_* values
    don't match the Docker container, so we bypass it for integration tests
    by reading `.env` directly via `dotenv_values`.

    Returns:
        Mapping of env vars from `.env`, empty if the file is absent.
    """
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return {}
    return {k: v for k, v in dotenv_values(env_path).items() if v is not None}


def _build_db_url() -> str | None:
    """Build an asyncpg URL for the live horrorbot DB.

    Priority order:
      1. `HORRORBOT_TEST_DB_URL` shell env — explicit override.
      2. `.env` values (real docker-compose vars).
      3. `os.environ` fallback (pytest-dotenv's `.env.test` placeholder
         values end up here; they usually point to a non-existent DB, but
         they're kept as last resort for CI setups without a `.env`).

    Returns:
        `postgresql+asyncpg://...` URL or None if key vars are missing.
    """
    explicit = os.environ.get("HORRORBOT_TEST_DB_URL")
    if explicit:
        return explicit

    shell = {k: v for k, v in os.environ.items() if v}
    real_env = _load_real_env()
    # real_env wins over shell so .env's docker-compose port (5434) overrides
    # pytest-dotenv's .env.test placeholder (5432, horrorbot_test).
    env = shell | real_env
    required = (
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER",
        "POSTGRES_PASSWORD", "POSTGRES_DB",
    )
    if not all(env.get(k) for k in required):
        return None
    return (
        f"postgresql+asyncpg://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
        f"@{env['POSTGRES_HOST']}:{env['POSTGRES_PORT']}/{env['POSTGRES_DB']}"
    )


async def _purge_test_rows(conn: AsyncConnection) -> None:
    """Remove any stale rows produced by previous integration runs.

    Args:
        conn: Active async connection.
    """
    await conn.execute(
        text("DELETE FROM films WHERE tmdb_id = ANY(:ids)"),
        {"ids": list(TEST_TMDB_IDS)},
    )
    await conn.commit()


@pytest.fixture
async def clean_db() -> AsyncGenerator[AsyncConnection, None]:
    """Async connection to the horrorbot DB with test-row cleanup around the test.

    Pre-clean and post-clean both delete synthetic tmdb_ids (TEST_TMDB_IDS)
    to keep real data untouched. Skips when the DB is unreachable.

    Yields:
        An `AsyncConnection` with transaction semantics (explicit commit).
    """
    url = _build_db_url()
    if url is None:
        pytest.skip("POSTGRES_* not configured for integration tests")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        conn = await engine.connect()
    except Exception as exc:  # noqa: BLE001 — we want any connection failure
        await engine.dispose()
        pytest.skip(f"Postgres unreachable: {exc}")

    try:
        await _purge_test_rows(conn)
        yield conn
    finally:
        try:
            await _purge_test_rows(conn)
        finally:
            await conn.close()
            await engine.dispose()


@pytest.fixture
def tmdb_extractor():
    """Real TMDBExtractor, skipped when TMDB_API_KEY is the placeholder.

    Running this fixture's tests requires exporting a real API key in the
    shell BEFORE pytest starts — `.env.test`'s placeholder value is
    detected and the test is skipped to avoid spurious 401 noise.

    Returns:
        A ready-to-use `TMDBExtractor` instance.
    """
    from src.etl.extractors.tmdb.tmdb import TMDBExtractor
    from src.settings import settings

    if not settings.tmdb.api_key or settings.tmdb.api_key == _TMDB_PLACEHOLDER_KEY:
        pytest.skip(
            "TMDB_API_KEY not configured — export a real key in the shell "
            "before invoking pytest (placeholder from .env.test detected)",
        )

    return TMDBExtractor()
