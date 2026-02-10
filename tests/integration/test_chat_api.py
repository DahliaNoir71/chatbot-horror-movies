"""Integration tests for the synchronous chat endpoint.

Tests cover:
- Chat responses for each intent type
- Response schema validation
- Multi-turn session persistence
- Input validation (empty message, invalid session_id)
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from tests.integration.conftest import (
    make_chat_result,
    make_mock_router,
    make_mock_session_manager,
)

# ============================================================================
# Per-intent tests
# ============================================================================

_INTENT_CASES = [
    ("greeting", "Bienvenue dans le monde de l'horreur !", "Bonjour"),
    ("horror_recommendation", "Je vous recommande The Conjuring (2013).", "Recommande-moi un film d'horreur"),
    ("horror_discussion", "Le genre horreur explore nos peurs.", "Pourquoi les gens aiment les films d'horreur ?"),
    ("film_details", "The Shining (1980) - Note : 8.4/10.", "Parle-moi de The Shining"),
    ("out_of_scope", "Je suis specialise dans les films d'horreur.", "Quelle est la capitale de la France ?"),
]


class TestChatByIntent:
    """POST /api/v1/chat — verify response for each intent."""

    @staticmethod
    @pytest.mark.parametrize("intent,response_text,message", _INTENT_CASES)
    async def test_chat_intent(
        client: AsyncClient,
        auth_headers: dict[str, str],
        intent: str,
        response_text: str,
        message: str,
    ) -> None:
        result = make_chat_result(text=response_text, intent=intent, confidence=0.90)
        mock_router = make_mock_router(result)

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat",
                json={"message": message},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == intent
        assert len(body["response"]) > 0


# ============================================================================
# Schema & session tests
# ============================================================================


class TestChatSchema:
    """Response schema and session management."""

    @staticmethod
    async def test_chat_returns_valid_session_id(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        with (
            patch("src.api.routers.chat.get_intent_router", return_value=make_mock_router()),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat",
                json={"message": "Salut"},
                headers=auth_headers,
            )
        body = resp.json()
        UUID(body["session_id"])  # must be a valid UUID

    @staticmethod
    async def test_chat_response_schema(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        result = make_chat_result(confidence=0.87)

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=make_mock_router(result)),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            resp = await client.post(
                "/api/v1/chat",
                json={"message": "Hello"},
                headers=auth_headers,
            )

        body = resp.json()
        assert set(body.keys()) == {"response", "intent", "confidence", "session_id"}
        assert isinstance(body["confidence"], float)
        assert 0.0 <= body["confidence"] <= 1.0

    @staticmethod
    async def test_chat_multi_turn_preserves_session(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        sid = uuid4()
        mock_router = make_mock_router(make_chat_result(session_id=sid))

        with (
            patch("src.api.routers.chat.get_intent_router", return_value=mock_router),
            patch("src.api.routers.chat.get_session_manager", return_value=make_mock_session_manager()),
        ):
            # First request — no session_id
            resp1 = await client.post(
                "/api/v1/chat",
                json={"message": "Bonjour"},
                headers=auth_headers,
            )
            returned_sid = resp1.json()["session_id"]

            # Second request — with session_id from first response
            await client.post(
                "/api/v1/chat",
                json={"message": "Recommande-moi un film", "session_id": returned_sid},
                headers=auth_headers,
            )

        # Verify the router was called with the correct session UUID
        second_call = mock_router.handle.call_args_list[1]
        passed_sid = second_call.kwargs.get("session_id") or (
            second_call.args[1] if len(second_call.args) > 1 else None
        )
        assert passed_sid == UUID(returned_sid)


# ============================================================================
# Validation tests
# ============================================================================


class TestChatValidation:
    """Input validation on the chat endpoint."""

    @staticmethod
    async def test_chat_invalid_session_id_400(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/chat",
            json={"message": "Bonjour", "session_id": "not-a-uuid"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @staticmethod
    async def test_chat_empty_message_422(
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/chat",
            json={"message": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422
