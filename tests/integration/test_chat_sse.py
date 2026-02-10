"""Integration tests for SSE streaming chat endpoint.

Tests cover:
- Content-Type verification
- Template intent (direct_text) single chunk
- LLM intent with multiple streamed chunks
- Done event metadata
- Chunk concatenation
- Session ID persistence
- Error handling (503)
- Auth enforcement
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from tests.integration.conftest import (
    make_mock_session_manager,
    parse_sse_events,
)


def _make_stream_router(
    *,
    token_iter=None,
    intent: str = "greeting",
    confidence: float = 0.95,
    session_id=None,
    direct_text: str | None = None,
    raise_exc: Exception | None = None,
) -> tuple[MagicMock, UUID]:
    """Build a mock IntentRouter configured for streaming.

    Returns (mock_router, session_uuid).
    """
    sid = session_id or uuid4()
    mock = MagicMock()
    if raise_exc:
        mock.handle_stream.side_effect = raise_exc
    else:
        mock.handle_stream.return_value = (
            token_iter,
            intent,
            confidence,
            sid,
            direct_text,
        )
    return mock, sid


# ============================================================================
# Streaming tests
# ============================================================================


class TestChatSSE:
    """POST /api/v1/chat/stream — Server-Sent Events."""

    @staticmethod
    async def test_stream_content_type(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        mock_router, _ = _make_stream_router(direct_text="Bonjour !")

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Salut"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    @staticmethod
    async def test_stream_template_single_chunk(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        mock_router, _ = _make_stream_router(
            direct_text="Bienvenue !",
            intent="greeting",
            confidence=0.93,
        )

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Bonjour"},
                headers=auth_headers,
            )

        events = parse_sse_events(resp.text)
        chunks = [e for e in events if e["type"] == "chunk"]
        dones = [e for e in events if e["type"] == "done"]
        assert len(chunks) == 1
        assert chunks[0]["content"] == "Bienvenue !"
        assert len(dones) == 1

    @staticmethod
    async def test_stream_llm_multiple_chunks(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        mock_router, _ = _make_stream_router(
            token_iter=iter(["Voici ", "quelques ", "films effrayants."]),
            intent="horror_recommendation",
            confidence=0.88,
        )

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Recommande-moi un film"},
                headers=auth_headers,
            )

        events = parse_sse_events(resp.text)
        chunks = [e for e in events if e["type"] == "chunk"]
        dones = [e for e in events if e["type"] == "done"]
        assert len(chunks) == 3
        assert len(dones) == 1

    @staticmethod
    async def test_stream_done_has_metadata(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        mock_router, _ = _make_stream_router(
            direct_text="Au revoir !",
            intent="farewell",
            confidence=0.91,
        )

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Au revoir"},
                headers=auth_headers,
            )

        events = parse_sse_events(resp.text)
        done = next(e for e in events if e["type"] == "done")
        assert done["intent"] == "farewell"
        assert isinstance(done["confidence"], float)
        assert "session_id" in done
        UUID(done["session_id"])

    @staticmethod
    async def test_stream_chunks_concatenate(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        mock_router, _ = _make_stream_router(
            token_iter=iter(["Les ", "films ", "d'horreur ", "japonais."]),
            intent="horror_discussion",
            confidence=0.86,
        )

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Parle-moi de l'horreur japonaise"},
                headers=auth_headers,
            )

        events = parse_sse_events(resp.text)
        chunks = [e for e in events if e["type"] == "chunk"]
        full_text = "".join(c["content"] for c in chunks)
        assert full_text == "Les films d'horreur japonais."

    @staticmethod
    async def test_stream_preserves_session(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        mock_router, expected_sid = _make_stream_router(
            direct_text="Salut !",
            intent="greeting",
            confidence=0.94,
        )

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Hello"},
                headers=auth_headers,
            )

        events = parse_sse_events(resp.text)
        done = next(e for e in events if e["type"] == "done")
        assert done["session_id"] == str(expected_sid)

    @staticmethod
    async def test_stream_error_returns_503(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        mock_router, _ = _make_stream_router(raise_exc=RuntimeError("LLM crashed"))

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Test error"},
                headers=auth_headers,
            )

        assert resp.status_code == 503

    @staticmethod
    async def test_stream_without_auth_denied(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Bonjour"},
        )
        # HTTPBearer returns 401 or 403 depending on FastAPI version
        assert resp.status_code in (401, 403)
