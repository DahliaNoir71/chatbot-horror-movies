"""Structured logging configuration for HorrorBot.

Configures structlog with JSON rendering, PII filtering (RGPD),
and request_id correlation via context variables.

Log level conventions:
    DEBUG    — Detailed diagnostic info (model loading steps, query plans)
    INFO     — Normal operations (request completed, model loaded)
    WARNING  — Client errors 4xx, degraded performance, retries
    ERROR    — Server errors 5xx, unhandled exceptions
    CRITICAL — Service down, data corruption, cannot recover
"""

import logging
import sys

import structlog

# =============================================================================
# PII FILTER (RGPD)
# =============================================================================

_PII_KEYS = frozenset(
    {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "email",
        "authorization",
        "secret",
        "secret_key",
        "api_key",
    }
)

_REDACTED = "***REDACTED***"


def pii_filter(
    logger: logging.Logger,
    _method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Scrub PII/sensitive values from log events.

    Replaces values whose keys match known sensitive field names
    with ``***REDACTED***``.

    Args:
        logger: Logger instance (unused, required by structlog API).
        method_name: Log method name (unused, required by structlog API).
        event_dict: Mutable log event dictionary.

    Returns:
        Sanitized event dictionary.
    """
    for key in event_dict:
        if key.lower() in _PII_KEYS:
            event_dict[key] = _REDACTED
    return event_dict


# =============================================================================
# CONFIGURATION
# =============================================================================


def configure_logging() -> None:
    """Configure structlog with JSON rendering, PII filtering, and contextvars.

    Call once at application startup (lifespan). After this call,
    ``structlog.get_logger()`` returns a logger bound to the shared
    configuration with automatic PII scrubbing and request_id injection.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        pii_filter,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Quiet noisy third-party loggers
    for name in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
