"""FastAPI application entry point.

Creates and configures the HorrorBot REST API with
authentication, rate limiting, and OpenAPI documentation.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.database import get_engine
from src.api.dependencies.rate_limit import check_rate_limit
from src.api.routers import chat, films
from src.api.schemas import (
    DatabaseComponentHealth,
    EmbeddingsComponentHealth,
    HealthComponents,
    HealthResponse,
    LLMComponentHealth,
    RegisterRequest,
    RegisterResponse,
    TokenRequest,
    TokenResponse,
)
from src.api.services.jwt_service import JWTService, get_jwt_service
from src.monitoring.middleware import PrometheusMiddleware, mount_metrics
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
    app.add_middleware(PrometheusMiddleware)
    mount_metrics(app)
    _register_routers(app)
    _mount_integration_client(app)
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
    app.include_router(chat.router, prefix="/api/v1")


def _mount_integration_client(app: FastAPI) -> None:
    """Mount the integration client as static files.

    Serves the HTML/JS demo client at ``/client/``.
    Mounted last so it doesn't shadow API routes.

    Args:
        app: FastAPI application instance.
    """
    from pathlib import Path

    client_dir = Path(__file__).resolve().parent.parent / "integration"
    if client_dir.is_dir():
        app.mount(
            "/client",
            StaticFiles(directory=str(client_dir), html=True),
            name="integration-client",
        )


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
        API health status with version and component details.
    """
    return HealthResponse(
        status="healthy",
        version=settings.api.version,
        components=_check_components(),
    )


def _check_components() -> HealthComponents:
    """Check health of all system components.

    Returns:
        Component health status.
    """
    return HealthComponents(
        llm=_check_llm(),
        database=_check_database(),
        embeddings=_check_embeddings(),
    )


def _check_llm() -> LLMComponentHealth:
    """Check LLM service status."""
    try:
        from src.services.llm.llm_service import get_llm_service

        service = get_llm_service()
        loaded = service._model is not None
        memory_mb = None
        if loaded:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss // (1024 * 1024)
        return LLMComponentHealth(loaded=loaded, memory_mb=memory_mb)
    except Exception:
        return LLMComponentHealth(loaded=False)


def _check_database() -> DatabaseComponentHealth:
    """Check database connection status."""
    try:
        from sqlalchemy import text as sa_text

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(sa_text("SELECT 1"))
        pool = engine.pool
        pool_available = pool.checkedin() if hasattr(pool, "checkedin") else None
        return DatabaseComponentHealth(connected=True, pool_available=pool_available)
    except Exception:
        return DatabaseComponentHealth(connected=False)


def _check_embeddings() -> EmbeddingsComponentHealth:
    """Check embeddings service status."""
    try:
        from src.services.embedding.embedding_service import get_embedding_service

        service = get_embedding_service()
        model_loaded = service._model is not None
        return EmbeddingsComponentHealth(model_loaded=model_loaded)
    except Exception:
        return EmbeddingsComponentHealth(model_loaded=False)


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
    """Validate user credentials against demo and registered users.

    Args:
        username: Username to validate.
        password: Password to validate.

    Returns:
        True if credentials are valid.
    """
    demo_users = settings.security.demo_users
    if demo_users.get(username) == password:
        return True
    return _registered_users.get(username) == password


# =============================================================================
# REGISTRATION
# =============================================================================

_registered_users: dict[str, str] = {}


@app.post(
    "/api/v1/auth/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Register new user",
    description="Create a new user account.",
    dependencies=[Depends(check_rate_limit)],
)
def register(request: RegisterRequest) -> RegisterResponse:
    """Register a new user.

    Args:
        request: Registration credentials.

    Returns:
        Confirmation with username.

    Raises:
        HTTPException: 409 if username already taken.
    """
    if request.username in settings.security.demo_users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    if request.username in _registered_users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    _registered_users[request.username] = request.password
    return RegisterResponse(
        username=request.username,
        message="User registered successfully",
    )


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
