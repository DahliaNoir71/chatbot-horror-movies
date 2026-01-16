"""Rate limiting dependency for FastAPI.

Provides in-memory rate limiting per IP address
with configurable requests per minute threshold.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from src.settings import settings

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class RateLimitBucket:
    """Token bucket for single IP address.

    Attributes:
        tokens: Current available request tokens.
        last_update: Timestamp of last token refill.
    """

    tokens: float
    last_update: float = field(default_factory=time.time)


# =============================================================================
# RATE LIMITER
# =============================================================================


class RateLimiter:
    """In-memory rate limiter using token bucket algorithm.

    Thread-safe implementation with automatic token refill.

    Attributes:
        _max_requests: Maximum requests per minute.
        _buckets: IP address to bucket mapping.
        _lock: Thread synchronization lock.
    """

    def __init__(self, max_requests_per_minute: int) -> None:
        """Initialize rate limiter.

        Args:
            max_requests_per_minute: Request limit per IP per minute.
        """
        self._max_requests = max_requests_per_minute
        self._refill_rate = max_requests_per_minute / 60.0
        self._buckets: dict[str, RateLimitBucket] = defaultdict(
            lambda: RateLimitBucket(tokens=float(self._max_requests))
        )
        self._lock = Lock()

    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed for given IP.

        Args:
            client_ip: Client IP address.

        Returns:
            True if request is allowed, False if rate limited.
        """
        with self._lock:
            bucket = self._buckets[client_ip]
            self._refill_bucket(bucket)
            return self._consume_token(bucket)

    def _refill_bucket(self, bucket: RateLimitBucket) -> None:
        """Refill tokens based on elapsed time.

        Args:
            bucket: Rate limit bucket to refill.
        """
        now = time.time()
        elapsed = now - bucket.last_update
        bucket.tokens = min(
            self._max_requests,
            bucket.tokens + elapsed * self._refill_rate,
        )
        bucket.last_update = now

    @staticmethod
    def _consume_token(bucket: RateLimitBucket) -> bool:
        """Attempt to consume one token from bucket.

        Args:
            bucket: Rate limit bucket.

        Returns:
            True if token consumed, False if bucket empty.
        """
        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True
        return False

    def get_remaining(self, client_ip: str) -> int:
        """Get remaining requests for IP.

        Args:
            client_ip: Client IP address.

        Returns:
            Number of remaining requests.
        """
        with self._lock:
            bucket = self._buckets[client_ip]
            self._refill_bucket(bucket)
            return int(bucket.tokens)


# =============================================================================
# SINGLETON & DEPENDENCY
# =============================================================================

_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create singleton rate limiter instance.

    Returns:
        Configured RateLimiter instance.
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(settings.security.rate_limit_per_minute)
    return _rate_limiter


def check_rate_limit(
    request: Request,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    """FastAPI dependency to enforce rate limiting.

    Args:
        request: FastAPI request object.
        limiter: Rate limiter instance.

    Raises:
        HTTPException: 429 if rate limit exceeded.
    """
    client_ip = _extract_client_ip(request)
    if not limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": "60"},
        )


def _extract_client_ip(request: Request) -> str:
    """Extract client IP from request headers.

    Handles X-Forwarded-For for reverse proxy setups.

    Args:
        request: FastAPI request object.

    Returns:
        Client IP address string.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
