"""Integration tests for user registration endpoint.

Tests cover:
- Successful registration with valid credentials and email
- Conflict when username or email already exists
- Pydantic validation on username/password/email
- Registered user can login after registration
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.conftest import TEST_OTHER_PASS, TEST_REGISTER_PASS, TEST_SHORT_PASS


class TestRegister:
    """POST /api/v1/auth/register — user registration."""

    @staticmethod
    async def test_register_success(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": TEST_REGISTER_PASS,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == "newuser"
        assert body["email"] == "newuser@example.com"
        assert body["message"] == "User registered successfully"

    @staticmethod
    async def test_register_conflict_existing_user(client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": TEST_REGISTER_PASS,
            },
        )
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "other@example.com",
                "password": TEST_OTHER_PASS,
            },
        )
        assert resp.status_code == 409
        assert "username" in resp.json()["detail"].lower()

    @staticmethod
    async def test_register_conflict_existing_email(client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "taken@example.com",
                "password": TEST_REGISTER_PASS,
            },
        )
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "otheruser",
                "email": "taken@example.com",
                "password": TEST_REGISTER_PASS,
            },
        )
        assert resp.status_code == 409
        assert "email" in resp.json()["detail"].lower()

    @staticmethod
    async def test_register_short_username(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "ab",
                "email": "ab@example.com",
                "password": TEST_REGISTER_PASS,
            },
        )
        assert resp.status_code == 422

    @staticmethod
    async def test_register_short_password(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": TEST_SHORT_PASS,
            },
        )
        assert resp.status_code == 422

    @staticmethod
    async def test_register_invalid_username_chars(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "user@name!",
                "email": "user@example.com",
                "password": TEST_REGISTER_PASS,
            },
        )
        assert resp.status_code == 422

    @staticmethod
    async def test_register_invalid_email(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "not-an-email",
                "password": TEST_REGISTER_PASS,
            },
        )
        assert resp.status_code == 422

    @staticmethod
    async def test_register_missing_email(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": TEST_REGISTER_PASS},
        )
        assert resp.status_code == 422


class TestRegisterThenLogin:
    """Verify registered users can authenticate."""

    @staticmethod
    async def test_registered_user_can_login(client: AsyncClient) -> None:
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": TEST_REGISTER_PASS,
            },
        )
        resp = await client.post(
            "/api/v1/auth/token",
            json={"username": "newuser", "password": TEST_REGISTER_PASS},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
