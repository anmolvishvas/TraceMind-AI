"""Asynchronous PostgreSQL database session and engine management."""

import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger("tracemind.database")

settings = get_settings()


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.0 models."""


engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    echo=settings.DEBUG,
    future=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Dependency injection generator yielding an active async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> dict[str, Any]:
    """Verify database connectivity and pgvector extension availability."""
    try:
        async with engine.connect() as conn:
            # 1. Connectivity probe
            result = await conn.execute(text("SELECT 1;"))
            ping = result.scalar() == 1

            # 2. Check pgvector extension
            ext_result = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
            )
            has_vector = ext_result.scalar() is not None

            return {
                "status": "healthy" if ping else "unhealthy",
                "connected": ping,
                "pgvector_extension": has_vector,
            }
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "connected": False,
            "pgvector_extension": False,
            "error": str(exc),
        }
