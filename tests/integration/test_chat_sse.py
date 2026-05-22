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

from src.services.intent.router import StreamEvent
from tests.integration.conftest import (
    make_mock_session_manager,
    parse_sse_events,
)


def _make_stream_router(
    *,
    token_iter=None,
    intent: str = "conversational",
    confidence: float = 0.95,
    session_id=None,
    direct_text: str | None = None,
    raise_exc: Exception | None = None,
) -> tuple[MagicMock, UUID]:
    """Build a mock IntentRouter whose handle_stream is an async generator.

    Returns (mock_router, session_uuid).
    """
    sid = session_id or uuid4()
    events: list[StreamEvent] = []
    if raise_exc is None:
        events.append(StreamEvent(type="stage", stage="classification"))
        if direct_text is not None:
            events.append(StreamEvent(type="chunk", content=direct_text))
        else:
            events.append(StreamEvent(type="stage", stage="retrieval"))
            events.append(StreamEvent(type="stage", stage="generation"))
            events.extend(StreamEvent(type="chunk", content=t) for t in (token_iter or []))
        events.append(
            StreamEvent(type="done", intent=intent, confidence=confidence, session_id=sid)
        )

    async def _handle_stream(**kwargs):
        if raise_exc is not None:
            raise raise_exc
        for event in events:
            yield event

    mock = MagicMock()
    mock.handle_stream = _handle_stream
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
            intent="conversational",
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
            intent="needs_database",
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
            intent="conversational",
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
        assert done["intent"] == "conversational"
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
            intent="needs_database",
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
            intent="conversational",
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
    async def test_stream_error_emits_error_event(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """A pipeline failure surfaces as a terminal SSE error event (HTTP 200)."""
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

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)
        assert any(e["type"] == "error" for e in events)

    @staticmethod
    async def test_stream_emits_pipeline_stages(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """RAG streams emit classification, retrieval and generation stages."""
        mock_router, _ = _make_stream_router(
            token_iter=iter(["Un ", "film."]),
            intent="needs_database",
            confidence=0.9,
        )

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat/stream",
                json={"message": "Recommande un film"},
                headers=auth_headers,
            )

        events = parse_sse_events(resp.text)
        stages = [e["stage"] for e in events if e["type"] == "stage"]
        assert stages == ["classification", "retrieval", "generation"]

    @staticmethod
    async def test_stream_without_auth_denied(client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Bonjour"},
        )
        # HTTPBearer returns 401 or 403 depending on FastAPI version
        assert resp.status_code in (401, 403)
