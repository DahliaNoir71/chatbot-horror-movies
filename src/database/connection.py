"""PostgreSQL connection pool management with SQLAlchemy 2.0.

Provides both synchronous and asynchronous database sessions
with proper connection pooling and lifecycle management.
"""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from src.settings import settings


class DatabaseConnection:
    """Manages PostgreSQL connection pools for sync and async operations.

    This class implements the Singleton pattern to ensure a single
    connection pool is shared across the application.

    Attributes:
        _instance: Singleton instance.
        _sync_engine: SQLAlchemy sync engine.
        _async_engine: SQLAlchemy async engine.
        _sync_session_factory: Sync session factory.
        _async_session_factory: Async session factory.

    Example:
        ```python
        db = DatabaseConnection()
        with db.session() as session:
            result = session.execute(text("SELECT 1"))
        ```
    """

    _instance: "DatabaseConnection | None" = None
    _initialized: bool = False

    def __new__(cls) -> "DatabaseConnection":
        """Create singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize connection pools if not already done."""
        if DatabaseConnection._initialized:
            return

        self._sync_engine = self._create_sync_engine()
        self._async_engine = self._create_async_engine()
        self._sync_session_factory = self._create_sync_session_factory()
        self._async_session_factory = self._create_async_session_factory()
        DatabaseConnection._initialized = True

    @staticmethod
    def _create_sync_engine() -> Engine:
        """Create synchronous SQLAlchemy engine with connection pooling.

        Returns:
            SQLAlchemy Engine configured with QueuePool.
        """
        return create_engine(
            settings.database.sync_url,
            poolclass=QueuePool,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.pool_overflow,
            pool_timeout=settings.database.pool_timeout,
            pool_pre_ping=True,
            echo=settings.debug,
        )

    @staticmethod
    def _create_async_engine() -> AsyncEngine:
        """Create asynchronous SQLAlchemy engine with connection pooling.

        Returns:
            SQLAlchemy AsyncEngine configured with QueuePool.
        """
        return create_async_engine(
            settings.database.async_url,
            poolclass=QueuePool,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.pool_overflow,
            pool_timeout=settings.database.pool_timeout,
            pool_pre_ping=True,
            echo=settings.debug,
        )

    def _create_sync_session_factory(self) -> sessionmaker[Session]:
        """Create synchronous session factory.

        Returns:
            Configured sessionmaker for sync sessions.
        """
        return sessionmaker(
            bind=self._sync_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    def _create_async_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Create asynchronous session factory.

        Returns:
            Configured async_sessionmaker for async sessions.
        """
        return async_sessionmaker(
            bind=self._async_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional sync session scope.

        Automatically commits on success, rolls back on exception,
        and closes the session when done.

        Yields:
            SQLAlchemy Session instance.

        Raises:
            Exception: Re-raises any exception after rollback.
        """
        session = self._sync_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @asynccontextmanager
    async def async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide a transactional async session scope.

        Automatically commits on success, rolls back on exception,
        and closes the session when done.

        Yields:
            SQLAlchemy AsyncSession instance.

        Raises:
            Exception: Re-raises any exception after rollback.
        """
        session = self._async_session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    def get_sync_session(self) -> Session:
        """Get a new sync session without context manager.

        Caller is responsible for commit/rollback/close.

        Returns:
            New SQLAlchemy Session instance.
        """
        return self._sync_session_factory()

    def get_async_session(self) -> AsyncSession:
        """Get a new async session without context manager.

        Caller is responsible for commit/rollback/close.

        Returns:
            New SQLAlchemy AsyncSession instance.
        """
        return self._async_session_factory()

    def check_connection(self) -> bool:
        """Test database connectivity with a simple query.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            with self.session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001
            return False

    async def check_connection_async(self) -> bool:
        """Test database connectivity asynchronously.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            async with self.async_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001
            return False

    def dispose(self) -> None:
        """Dispose all connection pools and release resources.

        Should be called during application shutdown.
        """
        self._sync_engine.dispose()
        self._async_engine.sync_engine.dispose()

    @property
    def sync_engine(self) -> Engine:
        """Get the underlying sync engine.

        Returns:
            SQLAlchemy Engine instance.
        """
        return self._sync_engine

    @property
    def async_engine(self) -> AsyncEngine:
        """Get the underlying async engine.

        Returns:
            SQLAlchemy AsyncEngine instance.
        """
        return self._async_engine


# =============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# =============================================================================

_db: DatabaseConnection | None = None


def get_database() -> DatabaseConnection:
    """Get the singleton DatabaseConnection instance.

    Creates the instance on first call (lazy initialization).

    Returns:
        DatabaseConnection singleton instance.
    """
    global _db  # noqa: PLW0603
    if _db is None:
        _db = DatabaseConnection()
    return _db


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for sync database sessions.

    Yields:
        SQLAlchemy Session with automatic transaction management.
    """
    db = get_database()
    with db.session() as session:
        yield session


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async database sessions.

    Yields:
        SQLAlchemy AsyncSession with automatic transaction management.
    """
    db = get_database()
    async with db.async_session() as session:
        yield session


def init_database() -> None:
    """Initialize database connection pool.

    Call during application startup to eagerly create connections.
    """
    db = get_database()
    if db.check_connection():
        print("✅ Database connection established")
    else:
        print("❌ Database connection failed")


def close_database() -> None:
    """Close database connection pool.

    Call during application shutdown to release resources.
    """
    global _db  # noqa: PLW0603
    if _db is not None:
        _db.dispose()
        _db = None
        print("✅ Database connections closed")
