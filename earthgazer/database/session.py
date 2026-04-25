"""
Database session management with connection pooling.

This module provides a centralized way to get database sessions
with proper connection pooling to avoid exhausting PostgreSQL connections.
"""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from earthgazer.settings import EarthGazerSettings

logger = logging.getLogger(__name__)

# Shared database engine (lazy initialization)
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the shared database engine with connection pooling."""
    global _engine
    if _engine is None:
        settings = EarthGazerSettings()
        _engine = create_engine(
            settings.database.url,
            echo=False,
            poolclass=QueuePool,
            pool_size=2,
            max_overflow=3,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        logger.debug("Created shared database engine with connection pooling")
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """
    Get a database session from the connection pool.

    Yields:
        SQLAlchemy Session object

    Usage:
        session = next(get_session())
        try:
            # use session
            session.commit()
        finally:
            session.close()

    Or with context manager pattern:
        for session in get_session():
            # use session
            break
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
