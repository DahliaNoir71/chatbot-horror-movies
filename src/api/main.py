"""FastAPI application entry point.

Creates and configures the HorrorBot REST API with
authentication, rate limiting, and OpenAPI documentation.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from src.api.database import get_engine
from src.api.dependencies.rate_limit import check_rate_limit
from src.api.routers import films
from src.api.schemas import HealthResponse, TokenRequest, TokenResponse
from src.api.services.jwt_service import JWTService, get_jwt_service
from src.settings import settings

# =============================================================================
# LIFESPAN
# =============================================================================


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Validates database connection on startup.

    Args:
        _app: FastAPI application instance.

    Yields:
        None after startup tasks complete.
    """
    _verify_database_connection()
    yield


def _verify_database_connection() -> None:
    """Verify database is accessible on startup."""
    from sqlalchemy import text

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


# =============================================================================
# APPLICATION FACTORY
# =============================================================================


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title=settings.api.title,
        version=settings.api.version,
        description="REST API for HorrorBot film recommendations",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    _configure_cors(app)
    _register_routers(app)
    return app


def _configure_cors(app: FastAPI) -> None:
    """Configure CORS middleware.

    Args:
        app: FastAPI application instance.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


def _register_routers(app: FastAPI) -> None:
    """Register API routers.

    Args:
        app: FastAPI application instance.
    """
    app.include_router(films.router, prefix="/api/v1")


# =============================================================================
# ROOT ENDPOINTS
# =============================================================================

app = create_app()


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Verify API is running and responsive.",
)
def health_check() -> HealthResponse:
    """Health check endpoint (no authentication required).

    Returns:
        API health status with version.
    """
    return HealthResponse(
        status="healthy",
        version=settings.api.version,
    )


@app.post(
    "/api/v1/auth/token",
    response_model=TokenResponse,
    tags=["Authentication"],
    summary="Get access token",
    description="Authenticate and receive JWT token.",
    dependencies=[Depends(check_rate_limit)],
)
def login(
    request: TokenRequest,
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> TokenResponse:
    """Authenticate user and return JWT token.

    Args:
        request: Login credentials.
        jwt_service: JWT service for token generation.

    Returns:
        JWT access token.

    Raises:
        HTTPException: 401 if credentials invalid.
    """
    if not _validate_credentials(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = jwt_service.create_token(subject=request.username)
    return TokenResponse(
        access_token=token,
        expires_in=jwt_service.expire_seconds,
    )


def _validate_credentials(username: str, password: str) -> bool:
    """Validate user credentials against configured demo users.

    Args:
        username: Username to validate.
        password: Password to validate.

    Returns:
        True if credentials are valid.
    """
    demo_users = settings.security.demo_users
    return demo_users.get(username) == password


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
    )
