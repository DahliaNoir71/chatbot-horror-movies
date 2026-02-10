"""Chat endpoints for HorrorBot conversational API.

Provides synchronous and streaming chat endpoints with
intent classification, RAG retrieval, and multi-turn sessions.
"""

import json
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from src.api.database import get_db
from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.rate_limit import check_rate_limit
from src.api.schemas import ChatRequest, ChatResponse, StreamChunk
from src.etl.utils.logger import setup_logger
from src.monitoring.metrics import (
    ACTIVE_SESSIONS,
    CHAT_ERRORS_TOTAL,
    CHAT_REQUEST_DURATION,
    CHAT_REQUESTS_TOTAL,
    SESSION_MESSAGE_COUNT,
)
from src.services.chat.session import get_session_manager
from src.services.intent.router import get_intent_router

logger = setup_logger("api.routers.chat")

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    dependencies=[Depends(check_rate_limit)],
)


# =============================================================================
# DEPENDENCIES
# =============================================================================


def _parse_session_id(session_id: str | None) -> UUID | None:
    """Parse session_id string to UUID.

    Args:
        session_id: Session ID string or None.

    Returns:
        UUID or None.

    Raises:
        HTTPException: 400 if session_id is not a valid UUID.
    """
    if session_id is None:
        return None
    try:
        return UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid session_id format: {session_id}. Must be a UUID.",
        ) from None


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post(
    "",
    response_model=ChatResponse,
    summary="Chat with HorrorBot",
    description="Send a message and get a synchronous response.",
)
def chat(
    request: ChatRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    """Synchronous chat endpoint.

    Args:
        request: Chat request with message and optional session_id.
        user: Authenticated user from JWT.
        db: Database session for film_details queries.

    Returns:
        ChatResponse with bot reply and metadata.
    """
    session_id = _parse_session_id(request.session_id)
    intent_router = get_intent_router()

    start = time.perf_counter()
    try:
        result = intent_router.handle(
            user_message=request.message,
            session_id=session_id,
            user_id=user.sub,
            db_session=db,
        )
        duration = time.perf_counter() - start

        CHAT_REQUESTS_TOTAL.labels(intent=result.intent, mode="sync").inc()
        CHAT_REQUEST_DURATION.labels(intent=result.intent).observe(duration)
        ACTIVE_SESSIONS.set(get_session_manager().active_count())

        session_history = get_session_manager().get_history_as_messages(result.session_id)
        SESSION_MESSAGE_COUNT.observe(len(session_history))

        return ChatResponse(
            response=result.text,
            intent=result.intent,
            confidence=round(result.confidence, 4),
            session_id=str(result.session_id),
        )

    except TimeoutError:
        CHAT_ERRORS_TOTAL.labels(error_type="timeout").inc()
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Le LLM a mis trop de temps a repondre. Essayez une question plus simple.",
        ) from None
    except Exception as exc:
        CHAT_ERRORS_TOTAL.labels(error_type="llm_crash").inc()
        logger.error(f"Chat error: {exc} (message: {request.message[:80]})")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de chat est temporairement indisponible. Reessayez.",
        ) from None


@router.post(
    "/stream",
    summary="Stream chat with HorrorBot",
    description="Send a message and receive a streamed SSE response.",
)
def chat_stream(
    request: ChatRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> EventSourceResponse:
    """Streaming chat endpoint via Server-Sent Events.

    Args:
        request: Chat request with message and optional session_id.
        user: Authenticated user from JWT.
        db: Database session for film_details queries.

    Returns:
        EventSourceResponse streaming JSON chunks.
    """
    session_id = _parse_session_id(request.session_id)
    intent_router = get_intent_router()

    start = time.perf_counter()
    try:
        token_iter, intent, confidence, sid, direct_text = intent_router.handle_stream(
            user_message=request.message,
            session_id=session_id,
            user_id=user.sub,
            db_session=db,
        )

        CHAT_REQUESTS_TOTAL.labels(intent=intent, mode="stream").inc()

    except TimeoutError:
        CHAT_ERRORS_TOTAL.labels(error_type="timeout").inc()
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Le LLM a mis trop de temps a repondre.",
        ) from None
    except Exception as exc:
        CHAT_ERRORS_TOTAL.labels(error_type="llm_crash").inc()
        logger.error(f"Chat stream error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de chat est temporairement indisponible.",
        ) from None

    # Sync generator — EventSourceResponse runs it in a thread pool
    def event_generator():
        """Generate SSE events from token stream."""
        accumulated_text = ""

        try:
            if direct_text is not None:
                chunk = StreamChunk(type="chunk", content=direct_text)
                yield json.dumps(chunk.model_dump(exclude_none=True))
                accumulated_text = direct_text
            else:
                for token in token_iter:
                    chunk = StreamChunk(type="chunk", content=token)
                    yield json.dumps(chunk.model_dump(exclude_none=True))
                    accumulated_text += token

            # Store assistant response in session
            session_mgr = get_session_manager()
            if accumulated_text:
                session_mgr.add_message(sid, "assistant", accumulated_text)

            duration = time.perf_counter() - start
            CHAT_REQUEST_DURATION.labels(intent=intent).observe(duration)
            ACTIVE_SESSIONS.set(session_mgr.active_count())

            done = StreamChunk(
                type="done",
                intent=intent,
                confidence=round(confidence, 4),
                session_id=str(sid),
            )
            yield json.dumps(done.model_dump(exclude_none=True))

        except Exception as exc:
            CHAT_ERRORS_TOTAL.labels(error_type="stream_error").inc()
            logger.error(f"Stream generation error: {exc}")
            yield json.dumps({"type": "error", "content": "Stream interrompu."})

    return EventSourceResponse(event_generator())
