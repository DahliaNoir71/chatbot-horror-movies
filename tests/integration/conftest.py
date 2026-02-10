"""Shared fixtures for G2 integration tests.

Uses the module-level ``app`` from ``src.api.main`` (which includes
all endpoints: auth, chat, films, health).  The database verification
in the lifespan is patched out so tests run without PostgreSQL.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.database import get_db
from src.services.intent.router import ChatResult

# ---------------------------------------------------------------------------
# Stable test session UUID
# ---------------------------------------------------------------------------

TEST_SESSION_ID = uuid4()

# ---------------------------------------------------------------------------
# ChatResult factory
# ---------------------------------------------------------------------------


def make_chat_result(
    text: str = "Bienvenue dans le monde de l'horreur !",
    intent: str = "greeting",
    confidence: float = 0.95,
    session_id=None,
) -> ChatResult:
    """Build a ``ChatResult`` with sensible defaults."""
    return ChatResult(
        text=text,
        intent=intent,
        confidence=confidence,
        session_id=session_id or TEST_SESSION_ID,
    )


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def make_mock_router(chat_result: ChatResult | None = None):
    """Return a mock IntentRouter whose ``.handle()`` returns *chat_result*."""
    mock = MagicMock()
    mock.handle.return_value = chat_result or make_chat_result()
    return mock


def make_mock_session_manager():
    """Return a mock SessionManager with safe defaults."""
    mock = MagicMock()
    mock.get_history_as_messages.return_value = []
    mock.active_count.return_value = 1
    mock.add_message.return_value = None
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an ``httpx.AsyncClient`` wired to the real app.

    * ``_verify_database_connection`` is patched to skip DB checks.
    * ``get_db`` is overridden with a mock.
    """
    from src.api.main import app

    with patch("src.api.main._verify_database_connection"):
        app.dependency_overrides[get_db] = lambda: MagicMock()
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Login with test credentials and return Authorization headers."""
    resp = await client.post(
        "/api/v1/auth/token",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------


def parse_sse_events(text: str) -> list[dict]:
    """Parse an SSE-formatted response body into a list of JSON dicts."""
    events: list[dict] = []
    for block in text.split("\n\n"):
        for line in block.strip().split("\n"):
            if line.startswith("data:"):
                raw = line[len("data:"):].strip()
                if not raw:
                    continue
                try:
                    events.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
    return events
