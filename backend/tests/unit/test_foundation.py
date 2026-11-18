from datetime import UTC, datetime

from httpx import AsyncClient
import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    DatabaseConnectionError,
    FileValidationException,
    RedisConnectionError,
    TraceMindBaseException,
)
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
    """Test that custom domain exceptions inherit from TraceMindBaseException."""
    exc = DatabaseConnectionError("Failed to reach DB", details={"host": "localhost"})
    assert isinstance(exc, TraceMindBaseException)
    assert exc.message == "Failed to reach DB"
    assert exc.details == {"host": "localhost"}

    redis_exc = RedisConnectionError("Redis down")
    assert isinstance(redis_exc, TraceMindBaseException)

    file_exc = FileValidationException("File too large")
    assert isinstance(file_exc, TraceMindBaseException)


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
    # Response code is either 200 (services ready) or 503 (not ready during local mock test)
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data
