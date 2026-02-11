"""T5 — Unit tests for SessionManager.

Tests session lifecycle, message management, and TTL expiration logic
with mocked time to avoid real delays. All tests are deterministic.

Note: Session/ChatMessage dataclasses use ``field(default_factory=time.time)``
which captures a direct reference to the built-in function at class-definition
time. Patching ``time.time`` via unittest.mock does NOT affect default_factory.
Therefore, expiration tests explicitly set ``session.last_active`` after creation.

Run:
    pytest tests/unit/test_session_manager.py -v
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from src.services.chat.session import SessionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Patch target for time.time calls inside SessionManager methods.
# NOTE: This only affects explicit ``time.time()`` calls in method bodies,
# NOT the dataclass ``default_factory=time.time`` (see module docstring).
_TIME_TARGET = "src.services.chat.session.time.time"


def _make_manager(max_history: int = 10, ttl_seconds: int = 10) -> SessionManager:
    """Create a SessionManager with test-friendly defaults."""
    return SessionManager(max_history=max_history, ttl_seconds=ttl_seconds)


# =========================================================================
# T5 — Session creation and retrieval
# =========================================================================


class TestSessionCreation:
    """T5 — get_or_create() logic."""

    @staticmethod
    def test_new_session_with_none_id():
        """Passing None creates a new session with a generated UUID."""
        manager = _make_manager()

        session = manager.get_or_create(None, "user1")

        assert isinstance(session.session_id, UUID)
        assert session.user_id == "user1"
        assert len(session.messages) == 0
        assert isinstance(session.created_at, float)
        assert session.created_at > 0

    @staticmethod
    def test_existing_session_returned():
        """Same session_id returns the same Session object."""
        manager = _make_manager()
        session1 = manager.get_or_create(None, "user1")
        sid = session1.session_id

        session2 = manager.get_or_create(sid, "user1")

        assert session2 is session1
        assert session2.session_id == sid

    @staticmethod
    def test_provided_id_used():
        """A provided UUID is used as the session ID."""
        manager = _make_manager()
        custom_id = uuid4()

        session = manager.get_or_create(custom_id, "user1")

        assert session.session_id == custom_id

    @staticmethod
    def test_retrieval_updates_last_active():
        """Retrieving an existing session updates last_active via time.time()."""
        with patch(_TIME_TARGET) as mock_time:
            # First get_or_create: cleanup + create (default_factory sets real time)
            mock_time.return_value = 1000.0
            manager = _make_manager(ttl_seconds=300)
            session = manager.get_or_create(None, "user1")
            initial_last_active = session.last_active

            # Second get_or_create: cleanup + explicit last_active = time.time()
            mock_time.return_value = 2000.0
            manager.get_or_create(session.session_id, "user1")

            # last_active should now be the mocked value (set explicitly in code)
            assert session.last_active == 2000.0
            assert session.last_active != initial_last_active


# =========================================================================
# T5 — Message management
# =========================================================================


class TestMessageManagement:
    """T5 — add_message() and get_history_as_messages()."""

    @staticmethod
    def test_add_message_appends():
        """Messages are appended to the session."""
        manager = _make_manager()
        session = manager.get_or_create(None, "user1")
        sid = session.session_id

        manager.add_message(sid, "user", "Bonjour")
        manager.add_message(sid, "assistant", "Bienvenue !")

        assert len(session.messages) == 2

    @staticmethod
    def test_messages_preserve_order():
        """Messages are stored in insertion order."""
        manager = _make_manager()
        session = manager.get_or_create(None, "user1")
        sid = session.session_id

        manager.add_message(sid, "user", "msg0")
        manager.add_message(sid, "assistant", "msg1")
        manager.add_message(sid, "user", "msg2")

        history = manager.get_history_as_messages(sid)
        assert [m["content"] for m in history] == ["msg0", "msg1", "msg2"]

    @staticmethod
    def test_trim_when_exceeding_max_history():
        """Oldest messages are trimmed when max_history is exceeded."""
        manager = _make_manager(max_history=3)
        session = manager.get_or_create(None, "user1")
        sid = session.session_id

        for i in range(5):
            manager.add_message(sid, "user", f"msg{i}")

        history = manager.get_history_as_messages(sid)
        assert len(history) == 3
        assert history[0]["content"] == "msg2"  # Oldest kept
        assert history[2]["content"] == "msg4"  # Most recent

    @staticmethod
    def test_add_to_nonexistent_session_ignored():
        """Adding a message to a non-existent session does nothing."""
        manager = _make_manager()
        fake_id = uuid4()

        # Should not raise
        manager.add_message(fake_id, "user", "Test")

        history = manager.get_history_as_messages(fake_id)
        assert history == []

    @staticmethod
    def test_get_history_returns_llm_format():
        """History is returned as list[dict] with 'role' and 'content' keys."""
        manager = _make_manager()
        session = manager.get_or_create(None, "user1")
        sid = session.session_id

        manager.add_message(sid, "user", "Salut")
        manager.add_message(sid, "assistant", "Bonjour !")

        history = manager.get_history_as_messages(sid)
        assert len(history) == 2
        for msg in history:
            assert set(msg.keys()) == {"role", "content"}
            assert isinstance(msg["role"], str)
            assert isinstance(msg["content"], str)


# =========================================================================
# T5 — TTL expiration (mocked time)
# =========================================================================


class TestSessionExpiration:
    """T5 — TTL-based session expiration with mocked time.

    Since ``Session.last_active`` is initially set by ``default_factory=time.time``
    (which bypasses the mock), we explicitly set ``session.last_active`` to a
    known value before testing expiration logic.
    """

    @staticmethod
    def test_cleanup_removes_expired():
        """Expired sessions are removed during cleanup."""
        with patch(_TIME_TARGET) as mock_time:
            mock_time.return_value = 1000.0
            manager = _make_manager(ttl_seconds=10)
            session = manager.get_or_create(None, "user1")
            # Pin last_active to our controlled time
            session.last_active = 1000.0
            assert manager.active_count() == 1

            # Advance time past TTL
            mock_time.return_value = 1015.0
            assert manager.active_count() == 0

    @staticmethod
    def test_cleanup_preserves_active():
        """Active sessions are preserved during cleanup."""
        with patch(_TIME_TARGET) as mock_time:
            mock_time.return_value = 1000.0
            manager = _make_manager(ttl_seconds=10)
            session = manager.get_or_create(None, "user1")
            session.last_active = 1000.0

            # Advance time but NOT past TTL
            mock_time.return_value = 1005.0
            assert manager.active_count() == 1

    @staticmethod
    def test_get_or_create_triggers_cleanup():
        """get_or_create cleans up expired sessions before creating new ones."""
        with patch(_TIME_TARGET) as mock_time:
            mock_time.return_value = 1000.0
            manager = _make_manager(ttl_seconds=10)
            session_old = manager.get_or_create(None, "user_old")
            session_old.last_active = 1000.0

            # Advance time past TTL, then create a new session
            mock_time.return_value = 1015.0
            session_new = manager.get_or_create(None, "user_new")

            # Old session expired, only new one remains
            assert manager.active_count() == 1
            assert session_new.user_id == "user_new"

    @staticmethod
    def test_get_history_nonexistent_returns_empty():
        """Getting history for a non-existent session returns empty list."""
        manager = _make_manager()

        history = manager.get_history_as_messages(uuid4())

        assert history == []


# =========================================================================
# T5 — Active session counting
# =========================================================================


class TestActiveCount:
    """T5 — active_count() behavior."""

    @staticmethod
    def test_active_count_zero_initially():
        """New manager has zero active sessions."""
        manager = _make_manager()
        assert manager.active_count() == 0

    @staticmethod
    def test_active_count_excludes_expired():
        """Expired sessions are excluded from active count."""
        with patch(_TIME_TARGET) as mock_time:
            mock_time.return_value = 1000.0
            manager = _make_manager(ttl_seconds=10)

            s1 = manager.get_or_create(None, "user1")
            s1.last_active = 1000.0
            s2 = manager.get_or_create(None, "user2")
            s2.last_active = 1000.0
            assert manager.active_count() == 2

            # Advance past TTL
            mock_time.return_value = 1015.0
            assert manager.active_count() == 0
