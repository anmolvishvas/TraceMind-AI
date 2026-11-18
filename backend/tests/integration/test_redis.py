import pytest

from app.core.redis import check_redis_health, close_redis, get_redis_client, get_redis_pool


@pytest.mark.asyncio
async def test_redis_health_check_structure() -> None:
    """Verify that check_redis_health returns expected contract."""
    health = await check_redis_health()
    assert "status" in health
    assert "connected" in health
    assert isinstance(health["connected"], bool)


@pytest.mark.asyncio
async def test_get_redis_pool_instance() -> None:
    """Verify Redis pool client initialization."""
    client = get_redis_pool()
    assert client is not None


@pytest.mark.asyncio
async def test_get_redis_dependency() -> None:
    """Verify get_redis_client dependency yields client."""
    client_gen = get_redis_client()
    client = await anext(client_gen)
    assert client is not None


@pytest.mark.asyncio
async def test_close_redis_lifecycle() -> None:
    """Verify close_redis releases resources without error."""
    await close_redis()
    # Calling a second time should also be safe (idempotent)
    await close_redis()
