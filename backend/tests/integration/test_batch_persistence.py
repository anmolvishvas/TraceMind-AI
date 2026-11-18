"""Integration tests for micro-batch log persistence, metrics, and search API."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import check_database_health
from app.schemas.log_event import CanonicalLogEvent
from app.services.log_service import IngestionResult, LogService


@pytest.fixture
def sample_events() -> list[CanonicalLogEvent]:
    """Generate sample canonical log events."""
    now = datetime.now(UTC)
    return [
        CanonicalLogEvent(
            event_id=f"evt-{i}",
            timestamp=now,
            severity="ERROR" if i % 2 == 0 else "INFO",
            service_name="payment-service" if i < 3 else "auth-service",
            environment="production",
            message=f"Log event message #{i}",
            error_signature="sig-hash-12345" if i % 2 == 0 else None,
        )
        for i in range(5)
    ]


@pytest.mark.asyncio
async def test_persist_batch_and_redis_metrics(sample_events: list[CanonicalLogEvent]) -> None:
    """Verify micro-batch persistence and Redis pipeline metric updates."""
    mock_db = AsyncMock()
    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock()
    mock_redis.pipeline.return_value = mock_pipe

    service = LogService(db=mock_db, redis_client=mock_redis)

    # Empty batch returns 0
    count_zero = await service.persist_batch([])
    assert count_zero == 0
    assert mock_db.execute.call_count == 0

    # Persist 5 events
    persisted = await service.persist_batch(sample_events)
    assert persisted == 5
    assert mock_db.execute.call_count == 1
    assert mock_db.commit.call_count == 1
    assert mock_pipe.incr.call_count > 0
    assert mock_pipe.execute.call_count == 1


@pytest.mark.asyncio
async def test_redis_metrics_failure_resilience(sample_events: list[CanonicalLogEvent]) -> None:
    """Ensure database persistence succeeds even if Redis pipeline raises an exception."""
    mock_db = AsyncMock()
    mock_redis = MagicMock()
    mock_redis.pipeline.side_effect = RuntimeError("Redis connection dropped")

    service = LogService(db=mock_db, redis_client=mock_redis)
    persisted = await service.persist_batch(sample_events)
    assert persisted == 5
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_ingest_stream_batches_correctly(sample_events: list[CanonicalLogEvent]) -> None:
    """Verify streaming ingestion collects metrics and persists in batches."""
    mock_db = AsyncMock()
    service = LogService(db=mock_db, redis_client=None)

    async def event_generator() -> AsyncIterator[CanonicalLogEvent]:
        for e in sample_events:
            yield e

    result: IngestionResult = await service.ingest_stream(
        event_stream=event_generator(),
        filename="test_app.log",
    )

    assert result.filename == "test_app.log"
    assert result.total_parsed == 5
    assert result.errors_detected == 3  # Events 0, 2, 4
    assert result.service_breakdown["payment-service"] == 3
    assert result.service_breakdown["auth-service"] == 2
    assert result.severity_breakdown["ERROR"] == 3
    assert result.severity_breakdown["INFO"] == 2


@pytest.mark.asyncio
async def test_search_logs_query_composition() -> None:
    """Verify search_logs generates parameterized queries."""
    mock_db = AsyncMock()
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 42

    mock_query_res = MagicMock()
    mock_query_res.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [mock_count_res, mock_query_res]

    service = LogService(db=mock_db)
    items, total = await service.search_logs(
        service_name="order-service",
        severity="ERROR",
        error_signature="sig-abc",
        query="timeout",
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        limit=10,
        offset=0,
    )
    assert total == 42
    assert items == []
    assert mock_db.execute.call_count == 2


@pytest.mark.asyncio
async def test_get_by_event_id_not_found() -> None:
    """Verify get_by_event_id returns None when event does not exist."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    service = LogService(db=mock_db)
    event = await service.get_by_event_id("non-existent-uuid")
    assert event is None


@pytest.mark.asyncio
async def test_api_upload_json_logs(async_client: AsyncClient) -> None:
    """End-to-end API test uploading structured JSON logs."""
    health = await check_database_health()
    if not health.get("connected"):
        pytest.skip("PostgreSQL test database is not available in local environment")

    json_lines = (
        '{"timestamp": "2026-11-18T10:00:00Z", "level": "info", "service": "api-gateway", "msg": "GET /status 200"}\n'
        '{"timestamp": "2026-11-18T10:00:01Z", "level": "error", "service": "api-gateway", "msg": "Upstream error 502"}\n'
    )
    files = {"file": ("production.json", json_lines.encode("utf-8"), "application/json")}

    response = await async_client.post(
        "/api/v1/logs/upload?service_name=api-gateway&environment=production",
        files=files,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "production.json"
    assert data["total_parsed"] == 2
    assert data["errors_detected"] == 1
    assert data["service_breakdown"]["api-gateway"] == 2


@pytest.mark.asyncio
async def test_api_upload_python_logs_with_traceback(async_client: AsyncClient) -> None:
    """End-to-end API test uploading Python logs with multi-line traceback."""
    health = await check_database_health()
    if not health.get("connected"):
        pytest.skip("PostgreSQL test database is not available in local environment")

    log_content = (
        "2026-11-18 10:15:30,123 [INFO] worker: Starting task\n"
        "2026-11-18 10:15:31,456 [ERROR] worker: Task failed with exception\n"
        "Traceback (most recent call last):\n"
        '  File "worker.py", line 42, in run\n'
        "    raise ValueError('Invalid worker payload')\n"
        "ValueError: Invalid worker payload\n"
        "2026-11-18 10:15:32,000 [INFO] worker: Task complete\n"
    )
    files = {"file": ("worker.log", log_content.encode("utf-8"), "text/plain")}

    response = await async_client.post(
        "/api/v1/logs/upload?service_name=worker&environment=production",
        files=files,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "worker.log"
    assert data["total_parsed"] == 3
    assert data["errors_detected"] == 1


@pytest.mark.asyncio
async def test_api_search_logs_endpoint(async_client: AsyncClient) -> None:
    """Verify GET /api/v1/logs/search returns paginated response."""
    health = await check_database_health()
    if not health.get("connected"):
        pytest.skip("PostgreSQL test database is not available in local environment")

    response = await async_client.get("/api/v1/logs/search?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "items" in data


@pytest.mark.asyncio
async def test_api_get_event_not_found(async_client: AsyncClient) -> None:
    """Verify GET /api/v1/logs/{event_id} returns 404 for unknown IDs."""
    health = await check_database_health()
    if not health.get("connected"):
        pytest.skip("PostgreSQL test database is not available in local environment")

    missing_id = str(uuid4())
    response = await async_client.get(f"/api/v1/logs/{missing_id}")
    assert response.status_code == 404
    data = response.json()
    assert f"'{missing_id}' was not found" in data["detail"]
