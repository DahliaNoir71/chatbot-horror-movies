"""JWT token generation and validation service.

Handles JWT creation, validation, and payload extraction
using HS256 algorithm as configured in settings.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt.exceptions import ExpiredSignatureError

from src.settings import settings

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass(frozen=True)
class TokenPayload:
    """Decoded JWT token payload.

    Attributes:
        sub: Subject (username or user ID).
        exp: Expiration timestamp.
        iat: Issued at timestamp.
    """

    sub: str
    exp: datetime
    iat: datetime


class JWTError(Exception):
    """Base exception for JWT operations."""

    pass


class TokenExpiredError(JWTError):
    """Raised when token has expired."""

    pass


class InvalidTokenError(JWTError):
    """Raised when token is malformed or invalid."""

    pass


# =============================================================================
# JWT SERVICE
# =============================================================================


class JWTService:
    """Service for JWT token operations.

    Attributes:
        _secret_key: Secret key for signing.
        _algorithm: JWT algorithm (HS256).
        _expire_minutes: Token lifetime in minutes.
    """

    def __init__(self) -> None:
        """Initialize JWT service from settings."""
        security = settings.security
        self._secret_key = security.jwt_secret_key
        self._algorithm = security.jwt_algorithm
        self._expire_minutes = security.jwt_expire_minutes

    def create_token(self, subject: str) -> str:
        """Generate a new JWT token.

        Args:
            subject: Token subject (username or user ID).

        Returns:
            Encoded JWT string.
        """
        now = datetime.now(UTC)
        payload = {
            "sub": subject,
            "iat": now,
            "exp": now + timedelta(minutes=self._expire_minutes),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_token(self, token: str) -> TokenPayload:
        """Decode and validate a JWT token.

        Args:
            token: Encoded JWT string.

        Returns:
            Decoded token payload.

        Raises:
            TokenExpiredError: If token has expired.
            InvalidTokenError: If token is malformed.
        """
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
            )
            return self._parse_payload(payload)
        except ExpiredSignatureError as e:
            raise TokenExpiredError("Token has expired") from e
        except InvalidTokenError as e:
            raise InvalidTokenError("Invalid token") from e

    @staticmethod
    def _parse_payload(payload: dict[str, Any]) -> TokenPayload:
        """Parse raw payload dict into TokenPayload.

        Args:
            payload: Decoded JWT payload dictionary.

        Returns:
            Structured TokenPayload instance.
        """
        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
        )

    @property
    def expire_seconds(self) -> int:
        """Get token lifetime in seconds."""
        return self._expire_minutes * 60


def get_jwt_service() -> JWTService:
    """Factory function for JWTService.

    Returns:
        Configured JWTService instance.
    """
    return JWTService()
