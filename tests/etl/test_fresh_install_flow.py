"""Fresh-install integration tests.

Validates that the post-0.A.1 schema (tsvector trigger + FR columns) and
the post-0.A.3 TMDB extractor (translations + alternative_titles) behave
correctly end-to-end against a live Postgres container.

Run locally against the running docker-compose DB:

    pytest tests/etl/test_fresh_install_flow.py -v -m "integration and not network"
    pytest tests/etl/test_fresh_install_flow.py -v -m integration  # includes network

The `clean_db` and `tmdb_extractor` fixtures live in `tests/etl/conftest.py`
and auto-skip when their prerequisites are not met.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from src.etl.extractors.tmdb.tmdb import TMDBExtractor


@pytest.mark.integration
async def test_tsvector_trigger_populates_on_insert(
    clean_db: AsyncConnection,
) -> None:
    """PostgreSQL trigger auto-populates both tsvector columns on INSERT."""
    await clean_db.execute(
        text(
            "INSERT INTO films (tmdb_id, title, title_fr, overview, overview_fr, director) "
            "VALUES (:id, :title, :title_fr, :overview, :overview_fr, :director)",
        ),
        {
            "id": 99001,
            "title": "Test Movie",
            "title_fr": "Film de Test",
            "overview": "A horror film",
            "overview_fr": "Un film d'horreur",
            "director": "Jane Doe",
        },
    )
    await clean_db.commit()

    row = (
        await clean_db.execute(
            text(
                "SELECT search_vector_fr, search_vector_en "
                "FROM films WHERE tmdb_id = :id",
            ),
            {"id": 99001},
        )
    ).first()

    assert row is not None
    assert row.search_vector_fr is not None
    assert row.search_vector_en is not None

    # Director must be indexed in both tsvectors (weight A in the trigger).
    match_en = (
        await clean_db.execute(
            text(
                "SELECT 1 FROM films WHERE tmdb_id = :id "
                "AND search_vector_en @@ plainto_tsquery('english', 'Jane Doe')",
            ),
            {"id": 99001},
        )
    ).first()
    assert match_en is not None

    match_fr = (
        await clean_db.execute(
            text(
                "SELECT 1 FROM films WHERE tmdb_id = :id "
                "AND search_vector_fr @@ plainto_tsquery('french', 'Film Test')",
            ),
            {"id": 99001},
        )
    ).first()
    assert match_fr is not None


@pytest.mark.integration
async def test_tsvector_trigger_regenerates_on_field_change(
    clean_db: AsyncConnection,
) -> None:
    """Trigger regenerates tsvector when a tracked source field changes."""
    await clean_db.execute(
        text("INSERT INTO films (tmdb_id, title) VALUES (:id, :title)"),
        {"id": 99002, "title": "Dummy"},
    )
    await clean_db.commit()

    await clean_db.execute(
        text("UPDATE films SET title_fr = :new WHERE tmdb_id = :id"),
        {"id": 99002, "new": "Nouveau Titre Français"},
    )
    await clean_db.commit()

    match = (
        await clean_db.execute(
            text(
                "SELECT 1 FROM films WHERE tmdb_id = :id "
                "AND search_vector_fr @@ plainto_tsquery('french', 'nouveau titre')",
            ),
            {"id": 99002},
        )
    ).first()
    assert match is not None


@pytest.mark.integration
@pytest.mark.network
def test_tmdb_extraction_produces_fr_fields(
    tmdb_extractor: TMDBExtractor,
) -> None:
    """Extraction from scratch populates FR fields for films that have them."""
    # (tmdb_id, expected_title_fr_or_none)
    # 9552  = The Exorcist → official FR title "L'Exorciste"
    # 381288 = Get Out → no expectation (depends on TMDB state)
    test_cases: list[tuple[int, str | None]] = [
        (9552, "L'Exorciste"),
        (381288, None),
    ]

    for tmdb_id, expected_fr in test_cases:
        bundle: dict[str, Any] | None = tmdb_extractor.extract_film(tmdb_id)
        assert bundle is not None, f"extract_film returned None for {tmdb_id}"
        film = bundle["film"]

        # The normalizer always sets these keys (via NotRequired defaults in
        # the TypedDict + unconditional writes in normalize_film).
        assert "title_fr" in film
        assert "overview_fr" in film
        assert "alternative_titles" in film

        if expected_fr is not None:
            assert film["title_fr"] == expected_fr, (
                f"tmdb_id={tmdb_id}: expected title_fr={expected_fr!r}, "
                f"got {film['title_fr']!r}"
            )
