import pytest
from sqlalchemy import text

from app.core.database import Base, check_database_health, engine, get_async_session


@pytest.mark.asyncio
async def test_database_health_check_structure() -> None:
    """Verify that check_database_health returns expected contract."""
    health = await check_database_health()
    assert "status" in health
    assert "connected" in health
    assert "pgvector_extension" in health
    assert isinstance(health["connected"], bool)


@pytest.mark.asyncio
async def test_get_async_session_dependency() -> None:
    """Verify that get_async_session yields a usable session."""
    session_generator = get_async_session()
    session = await anext(session_generator)
    assert session is not None
    await session.close()


def test_base_metadata_defined() -> None:
    """Verify SQLAlchemy 2.0 Base declarative class is initialized."""
    assert Base.metadata is not None
