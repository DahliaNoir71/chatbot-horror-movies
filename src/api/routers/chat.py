"""Chat endpoints for HorrorBot conversational API.

Provides synchronous and streaming chat endpoints with
intent classification, RAG retrieval, and multi-turn sessions.
"""

import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.rate_limit import check_rate_limit
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatSourceDocument,
    ChatTimings,
    StreamChunk,
)
from src.etl.utils.logger import setup_logger
from src.monitoring.metrics import (
    ACTIVE_SESSIONS,
    CHAT_ERRORS_TOTAL,
    CHAT_REQUEST_DURATION,
    CHAT_REQUESTS_TOTAL,
    SESSION_MESSAGE_COUNT,
)
from src.services.chat.session import get_session_manager
from src.services.intent.router import StreamEvent, get_intent_router

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


def _build_sources(documents: list) -> list[ChatSourceDocument]:
    """Map retrieved RAG documents to source DTOs for the API response.

    Args:
        documents: Retrieved documents with `source_id`, `metadata`,
            `similarity` and optional `rerank_score`.

    Returns:
        List of ChatSourceDocument, one per document.
    """
    return [
        ChatSourceDocument(
            tmdb_id=doc.source_id,
            title=doc.metadata.get("title", "Unknown"),
            year=doc.metadata.get("year"),
            similarity_score=round(doc.similarity, 4),
            rerank_score=(round(doc.rerank_score, 4) if doc.rerank_score is not None else None),
        )
        for doc in documents
    ]


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post(
    "",
    summary="Chat with HorrorBot",
    description="Send a message and get a synchronous response.",
)
async def chat(
    request: ChatRequest,
    user: CurrentUser,
) -> ChatResponse:
    """Chat endpoint returning a complete response.

    Args:
        request: Chat request with message and optional session_id.
        user: Authenticated user from JWT.

    Returns:
        ChatResponse with bot reply and metadata.
    """
    session_id = _parse_session_id(request.session_id)
    intent_router = get_intent_router()

    start = time.perf_counter()
    try:
        result = await intent_router.handle(
            user_message=request.message,
            session_id=session_id,
            user_id=user.sub,
        )
        duration = time.perf_counter() - start

        CHAT_REQUESTS_TOTAL.labels(intent=result.intent, mode="sync").inc()
        CHAT_REQUEST_DURATION.labels(intent=result.intent).observe(duration)
        ACTIVE_SESSIONS.set(get_session_manager().active_count())

        session_history = get_session_manager().get_history_as_messages(result.session_id)
        SESSION_MESSAGE_COUNT.observe(len(session_history))

        sources = _build_sources(result.documents)

        timings = ChatTimings(
            classification_ms=round(result.classification_ms, 1),
            retrieval_ms=round(result.retrieval_ms, 1) if result.retrieval_ms else None,
            rerank_ms=round(result.rerank_ms, 1) if result.rerank_ms else None,
            generation_ms=round(result.generation_ms, 1) if result.generation_ms else None,
            total_ms=round(result.total_ms, 1),
        )

        return ChatResponse(
            response=result.text,
            intent=result.intent,
            confidence=round(result.confidence, 4),
            session_id=str(result.session_id),
            sources=sources,
            timings=timings,
            token_usage=result.usage,
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


def _record_stream_metrics(intent: str, start: float) -> None:
    """Record request count, duration and active sessions for a stream.

    Args:
        intent: Intent label of the completed stream.
        start: perf_counter timestamp captured when the request began.
    """
    CHAT_REQUESTS_TOTAL.labels(intent=intent, mode="stream").inc()
    CHAT_REQUEST_DURATION.labels(intent=intent).observe(time.perf_counter() - start)
    ACTIVE_SESSIONS.set(get_session_manager().active_count())


def _event_to_sse(event: StreamEvent) -> str:
    """Serialise a domain StreamEvent into an SSE JSON payload.

    Args:
        event: Domain event from IntentRouter.handle_stream.

    Returns:
        JSON string for one SSE `data:` frame.
    """
    if event.type == "stage":
        chunk = StreamChunk(type="stage", stage=event.stage)
    elif event.type == "chunk":
        chunk = StreamChunk(type="chunk", content=event.content)
    else:
        confidence = round(event.confidence, 4) if event.confidence is not None else None
        chunk = StreamChunk(
            type="done",
            intent=event.intent,
            confidence=confidence,
            session_id=str(event.session_id),
            sources=_build_sources(event.documents) or None,
        )
    return json.dumps(chunk.model_dump(exclude_none=True))


@router.post(
    "/stream",
    summary="Stream chat with HorrorBot",
    description="Send a message and receive a streamed SSE response.",
)
async def chat_stream(
    request: ChatRequest,
    user: CurrentUser,
) -> EventSourceResponse:
    """Streaming chat endpoint via Server-Sent Events.

    Pipeline stage markers, text chunks and final metadata are pushed as
    SSE events. Once the stream is open an HTTP status can no longer be
    sent, so failures surface as a terminal `error` event.

    Args:
        request: Chat request with message and optional session_id.
        user: Authenticated user from JWT.

    Returns:
        EventSourceResponse streaming JSON-encoded StreamChunk events.
    """
    session_id = _parse_session_id(request.session_id)
    intent_router = get_intent_router()
    start = time.perf_counter()

    async def event_generator():
        """Map domain stream events to SSE frames, recording metrics."""
        intent_label = "unknown"
        try:
            async for event in intent_router.handle_stream(
                user_message=request.message,
                session_id=session_id,
                user_id=user.sub,
            ):
                if event.type == "done":
                    intent_label = event.intent or intent_label
                yield _event_to_sse(event)
            _record_stream_metrics(intent_label, start)
        except Exception as exc:
            CHAT_ERRORS_TOTAL.labels(error_type="stream_error").inc()
            logger.error(f"Chat stream error: {exc}")
            error = StreamChunk(type="error", content="Une erreur est survenue. Réessayez.")
            yield json.dumps(error.model_dump(exclude_none=True))

    return EventSourceResponse(event_generator())
