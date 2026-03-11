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
from sqlalchemy.orm import Session

from src.api.database import get_db, get_engine
from src.api.dependencies.auth import AdminUser
from src.api.dependencies.rate_limit import check_rate_limit
from src.api.routers import chat, films
from src.api.schemas import (
    AdminTokenRequest,
    DatabaseComponentHealth,
    EmbeddingsComponentHealth,
    HealthComponents,
    HealthResponse,
    LLMComponentHealth,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserTokenRequest,
)
from src.api.services.jwt_service import JWTService, get_jwt_service
from src.api.services.password_service import hash_password, verify_password
from src.database.models.auth.user import User
from src.database.repositories.auth.user import UserRepository
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
    _ensure_schema_up_to_date()
    _seed_admin_account()
    yield


def _verify_database_connection() -> None:
    """Verify database is accessible on startup."""
    from sqlalchemy import text

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _ensure_schema_up_to_date() -> None:
    """Apply lightweight schema migrations for columns added after initial deploy."""
    import logging

    from sqlalchemy import text

    logger = logging.getLogger("horrorbot.schema")
    engine = get_engine()

    migrations = [
        (
            "users",
            "role",
            "ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'",
        ),
    ]

    with engine.connect() as conn:
        for table, column, ddl in migrations:
            result = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :table AND column_name = :column"
                ),
                {"table": table, "column": column},
            )
            if not result.first():
                conn.execute(text(ddl))
                conn.commit()
                logger.info("Added column %s.%s", table, column)


def _seed_admin_account() -> None:
    """Create default admin account if none exists in DB."""
    import logging

    logger = logging.getLogger("horrorbot.admin")

    admin_emails = settings.security.admin_allowed_emails
    if not admin_emails:
        return

    engine = get_engine()
    from sqlalchemy.orm import Session as SASession

    with SASession(engine) as db:
        repo = UserRepository(db)
        admin_email = admin_emails[0]

        existing = repo.get_by_email(admin_email)
        if existing:
            changed = False
            if existing.role != "admin":
                existing.role = "admin"
                changed = True
            if not verify_password(
                settings.security.admin_default_password, existing.password_hash
            ):
                existing.password_hash = hash_password(settings.security.admin_default_password)
                changed = True
            if changed:
                db.commit()
                logger.info("Admin account updated (%s)", admin_email)
            else:
                logger.info("Admin account already exists (%s)", admin_email)
            return

        username = admin_email.split("@")[0]
        admin_user = User(
            username=username,
            email=admin_email,
            password_hash=hash_password(settings.security.admin_default_password),
            role="admin",
        )
        repo.create(admin_user)
        logger.info("Admin account created (%s / %s)", username, admin_email)


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
    tags=["Health"],
    summary="Health check",
    description="Verify API is running and responsive.",
)
def health_check(_user: AdminUser) -> HealthResponse:
    """Health check endpoint (admin only).

    Args:
        _user: Authenticated admin user.

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
    tags=["Authentication"],
    summary="Get user access token",
    description="Authenticate chatbot user with username and password.",
    dependencies=[Depends(check_rate_limit)],
)
def login(
    request: UserTokenRequest,
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate chatbot user and return JWT token.

    Args:
        request: Login credentials (username + password).
        jwt_service: JWT service for token generation.
        db: Database session.

    Returns:
        JWT access token.

    Raises:
        HTTPException: 401 if credentials invalid.
    """
    repo = UserRepository(db)
    user = repo.get_by_username(request.username)
    if user and user.role != "admin" and verify_password(request.password, user.password_hash):
        token = jwt_service.create_token(subject=user.username, role=user.role)
        return TokenResponse(
            access_token=token,
            expires_in=jwt_service.expire_seconds,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.post(
    "/api/v1/auth/admin/token",
    tags=["Authentication"],
    summary="Get admin access token",
    description="Authenticate admin with email and password.",
    dependencies=[Depends(check_rate_limit)],
)
def admin_login(
    request: AdminTokenRequest,
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate admin and return JWT token.

    Args:
        request: Login credentials (email + password).
        jwt_service: JWT service for token generation.
        db: Database session.

    Returns:
        JWT access token.

    Raises:
        HTTPException: 401 if credentials invalid.
    """
    repo = UserRepository(db)
    user = repo.get_by_email(request.email)
    if user and user.role == "admin" and verify_password(request.password, user.password_hash):
        token = jwt_service.create_token(subject=user.username, role=user.role)
        return TokenResponse(
            access_token=token,
            expires_in=jwt_service.expire_seconds,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


# =============================================================================
# REGISTRATION
# =============================================================================


@app.post(
    "/api/v1/auth/register",
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Register new user",
    description="Create a new user account.",
    dependencies=[Depends(check_rate_limit)],
)
def register(
    request: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RegisterResponse:
    """Register a new user.

    Args:
        request: Registration credentials.
        db: Database session.

    Returns:
        Confirmation with username and email.

    Raises:
        HTTPException: 409 if username or email already taken.
    """
    repo = UserRepository(db)

    if repo.username_exists(request.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    if repo.email_exists(request.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already taken",
        )

    role = "admin" if settings.security.is_admin_email(request.email) else "user"
    user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
        role=role,
    )
    repo.create(user)

    return RegisterResponse(
        username=user.username,
        email=user.email,
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
