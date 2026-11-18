from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from pydantic import ValidationError
import pytest

from app.api.deps import get_db_session, get_redis
from app.core.config import Settings, get_settings
from app.core.database import check_database_health
from app.core.exceptions import (
    AnomalyDetectionException,
    DatabaseConnectionError,
    FileValidationException,
    IncidentCorrelationException,
    LLMInferenceException,
    LogParsingException,
    MCPToolException,
    RAGRetrievalException,
    RedisConnectionError,
    TraceMindBaseException,
)
from app.core.redis import check_redis_health
from app.schemas.log_event import CanonicalLogEvent


def test_settings_initialization() -> None:
    """Test that application settings load with valid defaults."""
    settings = get_settings()
    assert settings.PROJECT_NAME == "TraceMind AI"
    assert settings.VERSION == "0.1.0"
    assert "postgresql+asyncpg://" in settings.async_database_url
    assert settings.POSTGRES_PORT == 5432
    assert settings.MAX_UPLOAD_SIZE_BYTES == 100 * 1024 * 1024


def test_settings_override() -> None:
    """Test custom configuration overrides."""
    custom_settings = Settings(
        ENVIRONMENT="production",
        POSTGRES_HOST="db.prod.internal",
        POSTGRES_PORT=5433,
    )
    assert custom_settings.ENVIRONMENT == "production"
    assert "db.prod.internal:5433" in custom_settings.async_database_url


def test_domain_exception_hierarchy() -> None:
    """Test that all domain exceptions inherit from TraceMindBaseException."""
    exceptions = [
        DatabaseConnectionError("DB error", details={"host": "localhost"}),
        RedisConnectionError("Redis error"),
        FileValidationException("Invalid file"),
        LogParsingException("Parse error"),
        AnomalyDetectionException("Anomaly error"),
        IncidentCorrelationException("Correlation error"),
        RAGRetrievalException("RAG error"),
        LLMInferenceException("LLM error"),
        MCPToolException("MCP error"),
    ]
    for exc in exceptions:
        assert isinstance(exc, TraceMindBaseException)
        assert exc.message is not None


def test_canonical_log_event_schema_valid() -> None:
    """Test valid instantiation of CanonicalLogEvent."""
    now = datetime.now(UTC)
    event = CanonicalLogEvent(
        timestamp=now,
        severity="ERROR",
        service_name="payment-gateway",
        message="Connection to upstream timed out after 3000ms",
        exception_type="TimeoutError",
        stack_trace="Traceback (most recent call last):\n  File 'app.py', line 42",
        error_signature="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        request_id="req-9876",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    )
    assert event.severity == "ERROR"
    assert event.service_name == "payment-gateway"
    assert event.event_id is not None
    assert event.metadata == {}


def test_canonical_log_event_invalid_severity() -> None:
    """Test that invalid log levels raise a Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        CanonicalLogEvent(
            severity="INVALID_LEVEL",  # type: ignore[arg-type]
            service_name="auth-service",
            message="Test message",
        )


def test_canonical_log_event_empty_service_name() -> None:
    """Test that empty service names raise validation errors."""
    with pytest.raises(ValidationError):
        CanonicalLogEvent(
            severity="INFO",
            service_name="",
            message="Test message",
        )


@pytest.mark.asyncio
async def test_api_deps_providers() -> None:
    """Verify that get_db_session and get_redis yield active resources."""
    db_gen = get_db_session()
    session = await anext(db_gen)
    assert session is not None
    await session.close()

    redis_gen = get_redis()
    client = await anext(redis_gen)
    assert client is not None


@pytest.mark.asyncio
async def test_check_database_health_failure_branch() -> None:
    """Test the failure branch of check_database_health."""
    with patch("app.core.database.engine.connect", side_effect=RuntimeError("Connection refused")):
        health = await check_database_health()
        assert health["status"] == "unhealthy"
        assert health["connected"] is False
        assert "error" in health


@pytest.mark.asyncio
async def test_check_redis_health_failure_branch() -> None:
    """Test the failure branch of check_redis_health."""
    mock_client = AsyncMock()
    mock_client.ping.side_effect = RuntimeError("Redis timeout")
    with patch("app.core.redis.get_redis_pool", return_value=mock_client):
        health = await check_redis_health()
        assert health["status"] == "unhealthy"
        assert health["connected"] is False
        assert "error" in health


@pytest.mark.asyncio
async def test_healthz_endpoint(async_client: AsyncClient) -> None:
    """Test the /healthz liveness endpoint."""
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["project"] == "TraceMind AI"
    assert data["version"] == "0.1.0"
    assert "environment" in data


@pytest.mark.asyncio
async def test_readyz_endpoint(async_client: AsyncClient) -> None:
    """Test the /api/v1/health/readyz readiness endpoint."""
    response = await async_client.get("/api/v1/health/readyz")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data
