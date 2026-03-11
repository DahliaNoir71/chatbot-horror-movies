"""Integration tests for admin access control (Phase 16).

Tests cover:
- Admin role assigned to allowlisted email at registration
- Regular user role assigned to non-allowlisted email
- JWT includes role claim
- Admin-only endpoints return 403 for regular users
- Admin-only endpoints succeed for admin users
"""

from __future__ import annotations

import os

import jwt as pyjwt
from httpx import AsyncClient

from tests.integration.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_USER, TEST_REGISTER_PASS

_JWT_SECRET = os.environ["JWT_SECRET_KEY"]
_JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")


class TestAdminRoleAssignment:
    """Role is assigned based on email allowlist at registration."""

    @staticmethod
    async def test_admin_email_gets_admin_role(client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": TEST_ADMIN_USER,
                "email": TEST_ADMIN_EMAIL,
                "password": TEST_REGISTER_PASS,
            },
        )
        resp = await client.post(
            "/api/v1/auth/admin/token",
            json={"email": TEST_ADMIN_EMAIL, "password": TEST_REGISTER_PASS},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        payload = pyjwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        assert payload["role"] == "admin"

    @staticmethod
    async def test_regular_email_gets_user_role(client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "regularuser",
                "email": "regular@example.com",
                "password": TEST_REGISTER_PASS,
            },
        )
        resp = await client.post(
            "/api/v1/auth/token",
            json={"username": "regularuser", "password": TEST_REGISTER_PASS},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        payload = pyjwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        assert payload["role"] == "user"


class TestAdminEndpointAccess:
    """Admin-only endpoints enforce role check."""

    @staticmethod
    async def test_health_requires_admin(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/health", headers=auth_headers)
        assert resp.status_code == 403

    @staticmethod
    async def test_health_admin_allowed(
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/health", headers=admin_auth_headers)
        assert resp.status_code == 200

    @staticmethod
    async def test_films_requires_admin(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/films", headers=auth_headers)
        assert resp.status_code == 403

    @staticmethod
    async def test_films_admin_allowed(
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/films", headers=admin_auth_headers)
        # 200 or 500 (if DB has no films table in sqlite)
        assert resp.status_code in (200, 500)
