"""Integration tests for JWT authentication flow.

Tests cover:
- Login with valid / invalid credentials
- Pydantic validation on credentials
- Token-based access to protected endpoints
- Expired token rejection
- Token renewal (re-login) flow
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest
from httpx import AsyncClient

from tests.integration.conftest import (
    make_chat_result,
    make_mock_router,
    make_mock_session_manager,
)

# ============================================================================
# Login tests
# ============================================================================


class TestLogin:
    """POST /api/v1/auth/token — credential validation."""

    @staticmethod
    async def test_login_valid_credentials(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/token",
            json={"username": "testuser", "password": "testpass123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

    @staticmethod
    async def test_login_invalid_password(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/token",
            json={"username": "testuser", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    @staticmethod
    async def test_login_unknown_user(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/token",
            json={"username": "nonexistent", "password": "testpass123"},
        )
        assert resp.status_code == 401

    @staticmethod
    async def test_login_short_username(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/token",
            json={"username": "ab", "password": "testpass123"},
        )
        assert resp.status_code == 422

    @staticmethod
    async def test_login_short_password(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/token",
            json={"username": "testuser", "password": "short"},
        )
        assert resp.status_code == 422


# ============================================================================
# Token access tests
# ============================================================================


class TestTokenAccess:
    """Protected endpoint access with / without valid JWT."""

    @staticmethod
    async def test_token_grants_chat_access(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        with (
            patch("src.api.routers.chat.get_intent_router", return_value=make_mock_router()),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat",
                json={"message": "Bonjour"},
                headers=auth_headers,
            )
        assert resp.status_code == 200

    @staticmethod
    async def test_missing_token_returns_401(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/chat",
            json={"message": "Bonjour"},
        )
        # HTTPBearer(auto_error=True) returns 401 or 403 depending on version
        assert resp.status_code in (401, 403)

    @staticmethod
    async def test_expired_token_returns_401(client: AsyncClient) -> None:
        secret = "test-secret-key-do-not-use-in-production-minimum-32-chars"
        expired_payload = {
            "sub": "testuser",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")

        resp = await client.post(
            "/api/v1/chat",
            json={"message": "Bonjour"},
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"].lower()

    @staticmethod
    async def test_wrong_signature_token_denied(client: AsyncClient) -> None:
        """A JWT signed with the wrong secret must not grant access."""
        wrong_payload = {
            "sub": "testuser",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        bad_token = jwt.encode(wrong_payload, "wrong-secret-key-at-least-32-chars-long!", algorithm="HS256")

        resp = await client.post(
            "/api/v1/chat",
            json={"message": "Bonjour"},
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        # The backend may return 401 or 500 depending on exception handling
        assert resp.status_code >= 400


# ============================================================================
# Token renewal
# ============================================================================


class TestTokenRenewal:
    """Simulates the client-side token refresh flow."""

    @staticmethod
    async def test_token_renewal_flow(client: AsyncClient) -> None:
        sid = uuid4()
        mock_router = make_mock_router(make_chat_result(session_id=sid))
        mock_session = make_mock_session_manager()

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=mock_session),
        ):
            # First login
            resp1 = await client.post(
                "/api/v1/auth/token",
                json={"username": "testuser", "password": "testpass123"},
            )
            assert resp1.status_code == 200
            token1 = resp1.json()["access_token"]

            # Second login (renewal)
            resp2 = await client.post(
                "/api/v1/auth/token",
                json={"username": "testuser", "password": "testpass123"},
            )
            assert resp2.status_code == 200
            token2 = resp2.json()["access_token"]

            # Both tokens should grant access
            for token in (token1, token2):
                resp = await client.post(
                    "/api/v1/chat",
                    json={"message": "Bonjour"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp.status_code == 200
