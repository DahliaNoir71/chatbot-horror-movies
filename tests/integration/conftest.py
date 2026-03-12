"""Shared fixtures for G2 integration tests.

Uses the module-level ``app`` from ``src.api.main`` (which includes
all endpoints: auth, chat, films, health).  The database verification
in the lifespan is patched out so tests run without PostgreSQL.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.database import get_db
from src.api.dependencies.rate_limit import check_rate_limit
from src.database.models.base import Base
from src.services.intent.router import ChatResult


# ---------------------------------------------------------------------------
# Auto-mark all tests in this directory as "integration"
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-apply ``@pytest.mark.integration`` to every test collected here."""
    integration_marker = pytest.mark.integration
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(integration_marker)


# ---------------------------------------------------------------------------
# Stable test session UUID
# ---------------------------------------------------------------------------

TEST_SESSION_ID = uuid4()

# Test-only credentials (never used outside tests)
TEST_DEMO_USER = "testuser"
TEST_DEMO_EMAIL = "testuser@example.com"
TEST_DEMO_PASS = "testpass123"  # noqa: S105
TEST_ADMIN_USER = "adminuser"
TEST_ADMIN_EMAIL = "serge.pfeiffer@proton.me"
TEST_ADMIN_PASS = "adminpass123"  # noqa: S105
TEST_REGISTER_PASS = "securepass123"  # noqa: S105
TEST_WRONG_PASS = "wrongpassword"  # noqa: S105
TEST_SHORT_PASS = "short"  # noqa: S105
TEST_OTHER_PASS = "otherpass456"  # noqa: S105

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
def _test_db_session() -> Generator[Session, None, None]:
    """Create an in-memory SQLite database with the users table for testing."""
    from src.database.models.auth.user import User

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    session_factory = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=[User.__table__])
        engine.dispose()


@pytest.fixture
async def client(_test_db_session: Session) -> AsyncGenerator[AsyncClient, None]:
    """Provide an ``httpx.AsyncClient`` wired to the real app.

    * ``_verify_database_connection`` is patched to skip DB checks.
    * ``get_db`` is overridden with an in-memory SQLite session.
    """
    from src.api.main import app

    def _override_get_db() -> Generator[Session, None, None]:
        try:
            yield _test_db_session
            _test_db_session.commit()
        except Exception:
            _test_db_session.rollback()
            raise

    with (
        patch("src.api.main._verify_database_connection"),
        patch("src.api.main._ensure_schema_up_to_date"),
    ):
        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[check_rate_limit] = lambda: None
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(check_rate_limit, None)


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Register a test user and return Authorization headers."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": TEST_DEMO_USER,
            "email": TEST_DEMO_EMAIL,
            "password": TEST_DEMO_PASS,
        },
    )
    assert reg_resp.status_code == 201, f"Register failed: {reg_resp.text}"

    resp = await client.post(
        "/api/v1/auth/token",
        json={"username": TEST_DEMO_USER, "password": TEST_DEMO_PASS},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_auth_headers(client: AsyncClient) -> dict[str, str]:
    """Register an admin user and return Authorization headers with admin role."""
    # Register with admin-allowed email
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": TEST_ADMIN_USER,
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASS,
        },
    )
    assert reg_resp.status_code == 201, f"Admin register failed: {reg_resp.text}"

    # Login to get admin JWT via admin endpoint
    resp = await client.post(
        "/api/v1/auth/admin/token",
        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASS},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
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


# ---------------------------------------------------------------------------
# Service mocks for RAG and Films API tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService to avoid loading ML model.

    Returns a mock that encodes text as a fixed 384-dimensional vector.
    """
    with patch("src.services.embedding.embedding_service.get_embedding_service") as mock:
        mock_service = MagicMock()
        mock_service.encode.return_value = [0.1] * 384  # Fixed 384-dim vector
        mock.return_value = mock_service
        yield mock


@pytest.fixture
def mock_retriever():
    """Mock DocumentRetriever with sample horror film documents.

    Simulates successful document retrieval for RAG pipeline tests.
    """
    from uuid import uuid4

    from src.services.rag.retriever import RetrievedDocument

    mock = MagicMock()
    mock.retrieve.return_value = [
        RetrievedDocument(
            id=uuid4(),
            content="The Conjuring (2013) is a supernatural horror film directed by James Wan. It's widely regarded as one of the best horror films of the 2010s.",
            source_type="film_overview",
            source_id=185,
            metadata={
                "title": "The Conjuring",
                "year": 2013,
                "rating": 7.5,
            },
            similarity=0.85,
        ),
        RetrievedDocument(
            id=uuid4(),
            content="Hereditary (2018) is a psychological horror film that explores themes of grief and family trauma.",
            source_type="film_overview",
            source_id=438631,
            metadata={
                "title": "Hereditary",
                "year": 2018,
                "rating": 8.3,
            },
            similarity=0.78,
        ),
    ]
    return mock


@pytest.fixture
def mock_llm_service():
    """Mock LLMService to avoid calling actual GGUF model.

    Provides deterministic responses for RAG pipeline tests.
    """
    mock = MagicMock()
    mock.generate_chat.return_value = {
        "text": "Je vous recommande The Conjuring (2013). C'est un film d'horreur classique très bien réalisé avec d'excellentes performances d'acteurs.",
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 50,
        },
    }
    mock.generate_stream.return_value = iter([
        "Je ",
        "vous ",
        "recommande ",
        "The ",
        "Conjuring. ",
    ])
    return mock


@pytest.fixture
def rag_pipeline(mock_retriever, mock_llm_service):
    """RAGPipeline with mocked dependencies.

    Used for testing RAG orchestration without real retrieval or LLM calls.
    """
    from src.services.rag.pipeline import RAGPipeline

    return RAGPipeline(retriever=mock_retriever, llm_service=mock_llm_service)


@pytest.fixture
def session_manager():
    """Fresh SessionManager instance for concurrency and TTL tests.

    Configured with short TTL (2 seconds) and small history (5 messages).
    """
    from src.services.chat.session import SessionManager

    return SessionManager(max_history=5, ttl_seconds=2)
