"""Asynchronous Redis client and sliding-window counter utilities."""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger("tracemind.redis")

settings = get_settings()

_redis_client: Redis[str] | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def get_redis_pool() -> Redis[str]:
    """Initialize or return the global Redis client pool bound to the active loop."""
    global _redis_client, _client_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _redis_client is None or (_client_loop is not None and _client_loop != current_loop):
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=3.0,
        )
        _client_loop = current_loop
    return _redis_client


async def close_redis() -> None:
    """Close active Redis connection pool gracefully."""
    global _redis_client, _client_loop
    if _redis_client is not None:
        try:
            if hasattr(_redis_client, "aclose"):
                await _redis_client.aclose()
            else:
                await _redis_client.close()
        except Exception as exc:
            logger.debug("Silently handling Redis close notice: %s", exc)
        finally:
            _redis_client = None
            _client_loop = None
            logger.info("Redis connection pool closed.")


async def get_redis_client() -> AsyncIterator[Redis[str]]:
    """Dependency injection generator yielding an async Redis client."""
    client = get_redis_pool()
    yield client


async def check_redis_health() -> dict[str, Any]:
    """Execute Redis ping probe to verify connectivity."""
    try:
        client = get_redis_pool()
        ping_result = await client.ping()
        return {
            "status": "healthy" if ping_result else "unhealthy",
            "connected": bool(ping_result),
        }
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(exc),
        }
