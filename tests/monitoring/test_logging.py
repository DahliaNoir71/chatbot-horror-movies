"""Tests for structured logging configuration and PII filtering."""

import json
import logging

import pytest
import structlog

from src.monitoring.logging_config import _PII_KEYS, _REDACTED, configure_logging, pii_filter


# =============================================================================
# PII FILTER — unit tests
# =============================================================================

_DUMMY_LOGGER = logging.getLogger("test")


class TestPIIFilter:
    """Tests for the pii_filter structlog processor."""

    @staticmethod
    def test_password_redacted() -> None:
        """password value is replaced with REDACTED."""
        event = pii_filter(_DUMMY_LOGGER, "info", {"event": "login", "password": "s3cret"})
        assert event["password"] == _REDACTED

    @staticmethod
    def test_access_token_redacted() -> None:
        """access_token value is replaced with REDACTED."""
        event = pii_filter(_DUMMY_LOGGER, "info", {"event": "auth", "access_token": "abc123"})
        assert event["access_token"] == _REDACTED

    @staticmethod
    @pytest.mark.parametrize("key", sorted(_PII_KEYS))
    def test_all_sensitive_keys_redacted(key) -> None:
        """Every key in _PII_KEYS is redacted."""
        event = pii_filter(_DUMMY_LOGGER, "info", {"event": "test", key: "sensitive_value"})
        assert event[key] == _REDACTED

    @staticmethod
    def test_non_sensitive_key_preserved() -> None:
        """Non-sensitive keys are left unchanged."""
        event = pii_filter(_DUMMY_LOGGER, "info", {"event": "test", "username": "alice"})
        assert event["username"] == "alice"

    @staticmethod
    def test_case_insensitive() -> None:
        """PII matching is case-insensitive (key.lower() comparison)."""
        event = pii_filter(_DUMMY_LOGGER, "info", {"event": "test", "Password": "s3cret"})
        assert event["Password"] == _REDACTED

    @staticmethod
    def test_event_field_preserved() -> None:
        """The event field itself is never redacted."""
        event = pii_filter(_DUMMY_LOGGER, "info", {"event": "user_login", "password": "x"})
        assert event["event"] == "user_login"

    @staticmethod
    def test_multiple_pii_keys_redacted() -> None:
        """Multiple PII fields in one event are all redacted."""
        event = pii_filter(
            _DUMMY_LOGGER,
            "info",
            {"event": "req", "password": "a", "token": "b", "email": "c@d.com"},
        )
        assert event["password"] == _REDACTED
        assert event["token"] == _REDACTED
        assert event["email"] == _REDACTED


# =============================================================================
# CONFIGURE LOGGING — integration tests
# =============================================================================


class TestConfigureLogging:
    """Tests for configure_logging() structlog setup."""

    @staticmethod
    def test_configure_logging_succeeds() -> None:
        """configure_logging() runs without raising."""
        configure_logging()

    @staticmethod
    def test_structlog_logger_is_usable() -> None:
        """After configuration, structlog.get_logger() returns a usable logger."""
        configure_logging()
        logger = structlog.get_logger("test")
        # Logger must support standard log methods
        assert callable(getattr(logger, "info", None))
        assert callable(getattr(logger, "warning", None))
        assert callable(getattr(logger, "error", None))

    @staticmethod
    def test_json_output_format(capsys) -> None:
        """Log output is valid JSON with expected keys."""
        configure_logging()
        logger = structlog.get_logger("test.json")
        logger.info("test_event", key="value")

        captured = capsys.readouterr()
        line = captured.out.strip().split("\n")[-1]
        data = json.loads(line)
        assert data["event"] == "test_event"
        assert "level" in data
        assert "timestamp" in data

    @staticmethod
    def test_pii_filtered_in_output(capsys) -> None:
        """PII values are redacted in actual log output."""
        configure_logging()
        logger = structlog.get_logger("test.pii")
        logger.info("auth_attempt", password="super_secret")

        captured = capsys.readouterr()
        line = captured.out.strip().split("\n")[-1]
        data = json.loads(line)
        assert data["password"] == _REDACTED
        assert "super_secret" not in captured.out

    @staticmethod
    def test_request_id_in_output(capsys) -> None:
        """request_id bound via contextvars appears in log output."""
        configure_logging()
        structlog.contextvars.bind_contextvars(request_id="abc-123-def")
        try:
            logger = structlog.get_logger("test.reqid")
            logger.info("with_request_id")

            captured = capsys.readouterr()
            line = captured.out.strip().split("\n")[-1]
            data = json.loads(line)
            assert data["request_id"] == "abc-123-def"
        finally:
            structlog.contextvars.clear_contextvars()
