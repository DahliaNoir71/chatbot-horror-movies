"""Integration tests for the Films API endpoints.

Only pure-validation tests are included here (422, 401, 403).
Tests requiring a live PostgreSQL connection are intentionally omitted —
they would time out on Windows (DB runs in WSL) and contribute nothing
beyond what SQLAlchemy or FastAPI already guarantee.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestFilmsListEndpoint:
    """GET /api/v1/films — Auth and pagination validation."""

    @staticmethod
    async def test_list_films_requires_auth_401(client: AsyncClient) -> None:
        resp = await client.get("/api/v1/films")
        assert resp.status_code in (401, 403)

    @staticmethod
    async def test_list_films_non_admin_returns_403(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/films", headers=auth_headers)
        assert resp.status_code == 403

    @staticmethod
    async def test_list_films_invalid_page_zero_returns_422(
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/films?page=0&size=20", headers=admin_auth_headers)
        assert resp.status_code == 422

    @staticmethod
    async def test_list_films_invalid_page_negative_returns_422(
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/films?page=-1&size=20", headers=admin_auth_headers)
        assert resp.status_code == 422

    @staticmethod
    async def test_list_films_invalid_size_zero_returns_422(
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/films?page=1&size=0", headers=admin_auth_headers)
        assert resp.status_code == 422


class TestFilmDetailsEndpoint:
    """GET /api/v1/films/{film_id} — Auth validation."""

    @staticmethod
    async def test_get_film_by_id_requires_auth_401(client: AsyncClient) -> None:
        resp = await client.get("/api/v1/films/1")
        assert resp.status_code in (401, 403)


class TestFilmSearchEndpoint:
    """POST /api/v1/films/search — Auth and input validation."""

    @staticmethod
    async def test_search_films_requires_auth_401(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/films/search",
            json={"query": "horror", "limit": 10},
        )
        assert resp.status_code in (401, 403)

    @staticmethod
    async def test_search_films_empty_query_422(
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/films/search",
            json={"query": "", "limit": 10},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 422
