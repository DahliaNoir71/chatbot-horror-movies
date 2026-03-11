"""Authentication dependencies for FastAPI.

Provides dependency injection for JWT token validation
and current user extraction from request headers.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.services.jwt_service import (
    InvalidTokenError,
    JWTService,
    TokenExpiredError,
    TokenPayload,
    get_jwt_service,
)

# =============================================================================
# SECURITY SCHEME
# =============================================================================

# HTTPBearer extracts token from "Authorization: Bearer <token>" header
security_scheme = HTTPBearer(
    scheme_name="JWT",
    description="Enter JWT token obtained from /api/v1/auth/token",
    auto_error=True,
)


# =============================================================================
# DEPENDENCIES
# =============================================================================


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials,
        Depends(security_scheme),
    ],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> TokenPayload:
    """Extract and validate current user from JWT token.

    Args:
        credentials: Bearer token from Authorization header.
        jwt_service: JWT service for token validation.

    Returns:
        Decoded token payload with user information.

    Raises:
        HTTPException: 401 if token is invalid or expired.
    """
    token = credentials.credentials
    try:
        return jwt_service.decode_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


# Type alias for cleaner endpoint signatures
CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]


def require_admin(
    current_user: CurrentUser,
) -> TokenPayload:
    """Require admin role for access.

    Args:
        current_user: Current authenticated user from JWT.

    Returns:
        Token payload if user is admin.

    Raises:
        HTTPException: 403 if user is not admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# Type alias for admin-only endpoints
AdminUser = Annotated[TokenPayload, Depends(require_admin)]
