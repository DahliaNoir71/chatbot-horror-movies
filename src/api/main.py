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
from src.database.models.auth.admin_user import AdminUser as AdminUserModel
from src.database.models.auth.chatbot_user import ChatbotUser
from src.database.repositories.auth.admin_user import AdminUserRepository
from src.database.repositories.auth.chatbot_user import ChatbotUserRepository
from src.monitoring.logging_config import configure_logging
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
    configure_logging()
    _verify_database_connection()
    _seed_admin_users()
    _seed_chatbot_users()
    _preload_models()
    yield


def _verify_database_connection() -> None:
    """Verify database is accessible on startup."""
    from sqlalchemy import text

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _seed_admin_users() -> None:
    """Seed admin users from settings on startup."""
    import logging

    from src.api.database import get_session_factory

    logger = logging.getLogger("horrorbot.seed")
    session = get_session_factory()()
    try:
        repo = AdminUserRepository(session)
        for email in settings.security.admin_allowed_emails:
            if not repo.email_exists(email):
                admin = AdminUserModel(
                    email=email,
                    password_hash=hash_password(settings.security.admin_default_password),
                )
                repo.create(admin)
                logger.info("Seeded admin user: %s", email)
        session.commit()
    finally:
        session.close()


def _seed_chatbot_users() -> None:
    """Seed chatbot users from AUTH_DEMO_USERS env var on startup.

    Format: "user1:pass1,user2:pass2" — synthetic email "{user}@horrorbot.local"
    is generated. Skips usernames already present in the database.
    """
    import logging

    from src.api.database import get_session_factory

    logger = logging.getLogger("horrorbot.seed")
    demo_users = settings.security.demo_users
    if not demo_users:
        return

    session = get_session_factory()()
    try:
        repo = ChatbotUserRepository(session)
        for username, password in demo_users.items():
            if not repo.username_exists(username):
                user = ChatbotUser(
                    username=username,
                    email=f"{username}@horrorbot.local",
                    password_hash=hash_password(password),
                )
                repo.create(user)
                logger.info("Seeded chatbot user: %s", username)
        session.commit()
    finally:
        session.close()


def _preload_models() -> None:
    """Pre-load AI models so they're ready for first request."""
    import logging

    logger = logging.getLogger("horrorbot.warmup")

    try:
        from src.services.embedding.embedding_service import get_embedding_service

        logger.info("Pre-loading embedding model...")
        _ = get_embedding_service().model
        logger.info("Embedding model loaded.")
    except Exception:
        logger.warning("Failed to pre-load embedding model", exc_info=True)

    try:
        from src.services.intent.classifier import get_intent_classifier

        logger.info("Pre-loading intent classifier...")
        _ = get_intent_classifier().pipeline
        logger.info("Intent classifier loaded.")
    except Exception:
        logger.warning("Failed to pre-load intent classifier", exc_info=True)

    try:
        from src.services.rag.reranker import get_reranker_service

        logger.info("Pre-loading reranker model...")
        get_reranker_service()._load_model()
        logger.info("Reranker model loaded.")
    except Exception:
        logger.warning("Failed to pre-load reranker model", exc_info=True)

    try:
        from src.services.llm.llm_service import get_llm_service

        logger.info("Pre-loading LLM...")
        _ = get_llm_service().llm
        logger.info("LLM loaded.")
    except Exception:
        logger.warning("Failed to pre-load LLM", exc_info=True)


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
        loaded = service._llm is not None
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
    repo = ChatbotUserRepository(db)
    user = repo.get_by_username(request.username)
    if user and verify_password(request.password, user.password_hash):
        token = jwt_service.create_token(subject=user.username, role="user")
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
    repo = AdminUserRepository(db)
    user = repo.get_by_email(request.email)
    if user and verify_password(request.password, user.password_hash):
        token = jwt_service.create_token(subject=user.email, role="admin")
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
    summary="Register new chatbot user",
    description="Create a new chatbot user account.",
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
    repo = ChatbotUserRepository(db)

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

    user = ChatbotUser(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
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
