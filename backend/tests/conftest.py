from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

import app.models  # noqa: F401
from app.core.database import Base, engine
from app.main import create_app


@pytest.fixture(autouse=True)
async def setup_test_tables() -> AsyncIterator[None]:
    """Ensure database schema is created for integration tests when DB is available."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        # Gracefully proceed if running in isolated unit test environment without active DB
        pass
    yield


@pytest.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    """Provide an asynchronous HTTP test client bound to the FastAPI app."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
