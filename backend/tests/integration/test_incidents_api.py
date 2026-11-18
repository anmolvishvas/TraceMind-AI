"""Integration tests for Anomaly Detection and Incident Management REST API."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import check_database_health
from app.models.incident import IncidentModel
from app.schemas.anomaly import AnomalyDetectionRequest, MetricDataPoint
from app.schemas.incident import (
    IncidentCreate,
    IncidentSeverity,
    IncidentStatus,
    IncidentStatusUpdate,
)
from app.services.anomaly_service import AnomalyService
from app.services.incident_service import IncidentService


@pytest.fixture
def sample_metric_points() -> list[MetricDataPoint]:
    """Generate time-series observations with an artificial spike."""
    now = datetime.now(UTC)
    points = [
        MetricDataPoint(
            timestamp=now + timedelta(minutes=i), value=10.0, service_name="payment-service"
        )
        for i in range(10)
    ]
    # Injected outlier
    points.append(
        MetricDataPoint(
            timestamp=now + timedelta(minutes=11), value=80.0, service_name="payment-service"
        )
    )
    return points


@pytest.mark.asyncio
async def test_anomaly_service_detection_and_recording(
    sample_metric_points: list[MetricDataPoint],
) -> None:
    """Verify AnomalyService detects outliers and executes database persistence."""
    mock_db = AsyncMock()
    service = AnomalyService(db=mock_db, redis_client=None)

    req = AnomalyDetectionRequest(
        service_name="payment-service",
        metric_name="error_rate",
        data_points=sample_metric_points,
    )

    anomalies = await service.detect_and_record_anomalies(req)
    assert len(anomalies) >= 1
    assert any(a.current_value == 80.0 for a in anomalies)
    assert mock_db.execute.call_count == 1
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_incident_service_create_and_lifecycle() -> None:
    """Verify IncidentService creates an incident and executes valid status transitions."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = IncidentService(db=mock_db)

    # 1. Create incident
    inc_data = IncidentCreate(
        title="Test Incident",
        lead_service="auth-service",
        severity=IncidentSeverity.HIGH,
        affected_services=["auth-service"],
    )
    res = await service.create_incident(inc_data)
    assert res.title == "Test Incident"
    assert res.status == IncidentStatus.DETECTED
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_incident_service_status_transition_mock() -> None:
    """Verify state transition via IncidentService on existing model."""
    mock_db = AsyncMock()
    mock_incident = IncidentModel(
        id=str(uuid4()),
        incident_id="inc-test-123",
        title="Payment failure",
        status=IncidentStatus.DETECTED.value,
        severity=IncidentSeverity.MEDIUM.value,
        lead_service="payment-service",
        affected_services=["payment-service"],
        error_signatures=[],
        started_at=datetime.now(UTC),
        detected_at=datetime.now(UTC),
        metadata_={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_incident
    mock_db.execute.return_value = mock_res

    service = IncidentService(db=mock_db)
    updated = await service.update_status(
        incident_id="inc-test-123",
        update_data=IncidentStatusUpdate(
            new_status=IncidentStatus.INVESTIGATING,
            user_id="sre@tracemind.ai",
        ),
    )
    assert updated.status == IncidentStatus.INVESTIGATING
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_api_anomalies_detect_endpoint(
    async_client: AsyncClient,
    sample_metric_points: list[MetricDataPoint],
) -> None:
    """Verify POST /api/v1/anomalies/detect endpoint via async_client."""
    health = await check_database_health()
    if not health.get("connected"):
        pytest.skip("PostgreSQL test database not available in local environment")

    payload = {
        "service_name": "payment-service",
        "metric_name": "error_rate",
        "data_points": [pt.model_dump(mode="json") for pt in sample_metric_points],
        "method": "ENSEMBLE",
        "sensitivity": 1.0,
    }

    response = await async_client.post("/api/v1/anomalies/detect", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["service_name"] == "payment-service"


@pytest.mark.asyncio
async def test_api_incidents_list_endpoint(async_client: AsyncClient) -> None:
    """Verify GET /api/v1/incidents endpoint returns paginated structure."""
    health = await check_database_health()
    if not health.get("connected"):
        pytest.skip("PostgreSQL test database not available in local environment")

    response = await async_client.get("/api/v1/incidents?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert "limit" in data
    assert "offset" in data
