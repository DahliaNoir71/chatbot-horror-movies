"""Database session management for FastAPI.

Provides SQLAlchemy engine and session dependency injection.
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.settings import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Get cached SQLAlchemy engine.

    Returns:
        Configured Engine instance with connection pooling.
    """
    db = settings.database
    return create_engine(
        db.sync_url,
        pool_size=db.pool_size,
        max_overflow=db.pool_overflow,
        pool_timeout=db.pool_timeout,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Get cached session factory.

    Returns:
        Configured sessionmaker instance.
    """
    return sessionmaker(
        bind=get_engine(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions.

    Yields:
        Database session, automatically closed after request.

    Example:
        @app.get("/films")
        def get_films(db: Session = Depends(get_db)):
            return db.query(Film).all()
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
