"""Shared dependency injection providers."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.redis import RedisClient, get_redis_client


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Provide transactional async database session."""
    async for session in get_async_session():
        yield session


async def get_redis() -> AsyncIterator[RedisClient]:
    """Provide active async Redis client."""
    async for redis in get_redis_client():
        yield redis
