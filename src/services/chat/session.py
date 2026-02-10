"""In-memory chat session management.

Stores conversation history per session for multi-turn context.
Sessions expire after configurable inactivity timeout.
"""

import threading
import time
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from src.etl.utils.logger import setup_logger

logger = setup_logger("services.chat.session")


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ChatMessage:
    """Single message in a conversation.

    Attributes:
        role: Message role (user, assistant, system).
        content: Message text content.
        timestamp: Unix timestamp of message creation.
    """

    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    """Chat session holding conversation history.

    Attributes:
        session_id: Unique session identifier.
        user_id: Authenticated user identifier.
        messages: Ordered list of conversation messages.
        created_at: Session creation timestamp.
        last_active: Last interaction timestamp.
    """

    session_id: UUID
    user_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


# =============================================================================
# SESSION MANAGER
# =============================================================================


class SessionManager:
    """In-memory session store with TTL-based expiration.

    Thread-safe implementation using a lock for concurrent access.
    Sessions are lazily cleaned up on access.

    Attributes:
        _sessions: Session ID to Session mapping.
        _max_history: Maximum messages to retain per session.
        _ttl_seconds: Session inactivity timeout in seconds.
        _lock: Thread synchronization lock.
    """

    def __init__(
        self,
        max_history: int = 10,
        ttl_seconds: int = 1800,
    ) -> None:
        """Initialize session manager.

        Args:
            max_history: Max messages to keep per session.
            ttl_seconds: Session expiry after inactivity (default 30 min).
        """
        self._sessions: dict[UUID, Session] = {}
        self._max_history = max_history
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._logger = logger

    def get_or_create(
        self,
        session_id: UUID | None,
        user_id: str,
    ) -> Session:
        """Get existing session or create a new one.

        Args:
            session_id: Existing session UUID, or None to create new.
            user_id: Authenticated user identifier.

        Returns:
            Active Session instance.
        """
        with self._lock:
            self._cleanup_expired()

            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                session.last_active = time.time()
                return session

            new_id = session_id or uuid4()
            session = Session(session_id=new_id, user_id=user_id)
            self._sessions[new_id] = session
            self._logger.debug(
                "session_created",
                session_id=str(new_id),
                user_id=user_id,
            )
            return session

    def add_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
    ) -> None:
        """Add a message to a session's history.

        Trims old messages if history exceeds max_history.

        Args:
            session_id: Session to add message to.
            role: Message role (user, assistant).
            content: Message text.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return

            session.messages.append(ChatMessage(role=role, content=content))
            session.last_active = time.time()

            if len(session.messages) > self._max_history:
                session.messages = session.messages[-self._max_history :]

    def get_history_as_messages(
        self,
        session_id: UUID,
    ) -> list[dict[str, str]]:
        """Get session history in LLM message format.

        Args:
            session_id: Session to retrieve history for.

        Returns:
            List of dicts with 'role' and 'content' keys.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return []
            return [{"role": msg.role, "content": msg.content} for msg in session.messages]

    def active_count(self) -> int:
        """Return count of active (non-expired) sessions."""
        with self._lock:
            self._cleanup_expired()
            return len(self._sessions)

    def _cleanup_expired(self) -> None:
        """Remove sessions that have exceeded TTL.

        Must be called with lock held.
        """
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items() if (now - s.last_active) > self._ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]
            self._logger.debug(f"Session expired: {sid}")


# =============================================================================
# SINGLETON
# =============================================================================

_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get singleton SessionManager instance.

    Returns:
        Configured SessionManager.
    """
    global _session_manager  # noqa: PLW0603
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
