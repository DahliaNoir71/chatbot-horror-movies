"""Integration tests for user registration endpoint.

Tests cover:
- Successful registration with valid credentials
- Conflict when username already exists (demo users or registered)
- Pydantic validation on username/password
- Registered user can login after registration
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _clear_registered_users():
    """Clear in-memory registered users between tests."""
    from src.api.main import _registered_users

    _registered_users.clear()
    yield
    _registered_users.clear()


class TestRegister:
    """POST /api/v1/auth/register — user registration."""

    @staticmethod
    async def test_register_success(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "securepass123"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == "newuser"
        assert body["message"] == "User registered successfully"

    @staticmethod
    async def test_register_conflict_demo_user(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "testuser", "password": "securepass123"},
        )
        assert resp.status_code == 409
        assert "already taken" in resp.json()["detail"].lower()

    @staticmethod
    async def test_register_conflict_existing_user(client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "securepass123"},
        )
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "otherpass456"},
        )
        assert resp.status_code == 409

    @staticmethod
    async def test_register_short_username(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "ab", "password": "securepass123"},
        )
        assert resp.status_code == 422

    @staticmethod
    async def test_register_short_password(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "short"},
        )
        assert resp.status_code == 422

    @staticmethod
    async def test_register_invalid_username_chars(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "user@name!", "password": "securepass123"},
        )
        assert resp.status_code == 422


class TestRegisterThenLogin:
    """Verify registered users can authenticate."""

    @staticmethod
    async def test_registered_user_can_login(client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "securepass123"},
        )
        resp = await client.post(
            "/api/v1/auth/token",
            json={"username": "newuser", "password": "securepass123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
