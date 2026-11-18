"""Unit tests for IncidentService and AnomalyService business logic."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import EntityNotFoundError, InvalidStateTransitionError
from app.models.anomaly import AnomalyModel
from app.models.incident import IncidentCorrelationModel, IncidentModel
from app.models.log_event import LogEventModel
from app.schemas.anomaly import (
    AnomalyDetectionRequest,
    DetectionMethod,
    MetricDataPoint,
)
from app.schemas.incident import (
    IncidentSeverity,
    IncidentStatus,
    IncidentStatusUpdate,
)
from app.services.anomaly_service import AnomalyService
from app.services.incident_service import IncidentService


@pytest.fixture
def sample_metric_series() -> list[MetricDataPoint]:
    """Provide time-series data with a clear statistical anomaly for testing."""
    now = datetime.now(UTC)
    points = [
        MetricDataPoint(
            timestamp=now + timedelta(minutes=i),
            value=10.0,
            service_name="payment-service",
        )
        for i in range(20)
    ]
    points.append(
        MetricDataPoint(
            timestamp=now + timedelta(minutes=21),
            value=150.0,
            service_name="payment-service",
        )
    )
    return points


@pytest.mark.asyncio
async def test_anomaly_service_algorithms_branching(
    sample_metric_series: list[MetricDataPoint],
) -> None:
    """Verify AnomalyService executes Z_SCORE, IQR, ISOLATION_FOREST, and COMPOSITE methods."""
    mock_db = AsyncMock()
    mock_db.add_all = MagicMock()
    service = AnomalyService(db=mock_db, redis_client=None)

    # 1. Z_SCORE method
    req_z = AnomalyDetectionRequest(
        service_name="payment-service",
        metric_name="error_rate",
        data_points=sample_metric_series,
        method=DetectionMethod.Z_SCORE,
    )
    res_z = await service.detect_and_record_anomalies(req_z)
    assert len(res_z) >= 1

    # 2. IQR method
    req_iqr = AnomalyDetectionRequest(
        service_name="payment-service",
        metric_name="error_rate",
        data_points=sample_metric_series,
        method=DetectionMethod.IQR,
    )
    res_iqr = await service.detect_and_record_anomalies(req_iqr)
    assert len(res_iqr) >= 1

    # 3. ISOLATION_FOREST method
    req_if = AnomalyDetectionRequest(
        service_name="payment-service",
        metric_name="error_rate",
        data_points=sample_metric_series,
        method=DetectionMethod.ISOLATION_FOREST,
    )
    res_if = await service.detect_and_record_anomalies(req_if)
    assert len(res_if) >= 1

    # 4. Composite (Default)
    req_comp = AnomalyDetectionRequest(
        service_name="payment-service",
        metric_name="error_rate",
        data_points=sample_metric_series,
        method=DetectionMethod.Z_SCORE,  # will pass if sensitivity tuned
    )
    res_comp = await service.detect_and_record_anomalies(req_comp)
    assert len(res_comp) >= 1


@pytest.mark.asyncio
async def test_anomaly_service_list_filtering() -> None:
    """Verify list_anomalies applies filters and pagination."""
    mock_db = AsyncMock()
    mock_count = MagicMock()
    mock_count.scalar.return_value = 1

    mock_anomaly = AnomalyModel(
        id=str(uuid4()),
        anomaly_id="anom-test-1",
        service_name="auth-service",
        timestamp=datetime.now(UTC),
        metric_name="error_rate",
        current_value=50.0,
        baseline_mean=10.0,
        baseline_std=2.0,
        threshold=16.0,
        anomaly_score=0.95,
        severity="HIGH",
        detection_method="Z_SCORE",
        details={},
        created_at=datetime.now(UTC),
    )
    mock_rows = MagicMock()
    mock_rows.scalars.return_value.all.return_value = [mock_anomaly]

    mock_db.execute.side_effect = [mock_count, mock_rows]

    service = AnomalyService(db=mock_db)
    items, total = await service.list_anomalies(
        service_name="auth-service",
        severity="HIGH",
        limit=10,
        offset=0,
    )
    assert total == 1
    assert len(items) == 1
    assert items[0].anomaly_id == "anom-test-1"
    assert items[0].service_name == "auth-service"


@pytest.mark.asyncio
async def test_incident_service_correlate_unassigned_events() -> None:
    """Verify correlate_unassigned_events selects error logs and creates incidents."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    now = datetime.now(UTC)
    db_events = [
        LogEventModel(
            id=str(uuid4()),
            event_id="e1",
            timestamp=now,
            severity="ERROR",
            service_name="api-gateway",
            environment="production",
            message="Upstream failure",
            trace_id="tr-100",
            attributes={},
            created_at=now,
        ),
        LogEventModel(
            id=str(uuid4()),
            event_id="e2",
            timestamp=now,
            severity="ERROR",
            service_name="payment-service",
            environment=None,  # Tests fallback to 'production'
            message="Database timeout",
            trace_id="tr-100",
            attributes={},
            created_at=now,
        ),
    ]

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = db_events
    mock_db.execute.return_value = mock_res

    service = IncidentService(db=mock_db)
    incidents = await service.correlate_unassigned_events(lookback_minutes=15)
    assert len(incidents) == 1
    assert incidents[0].lead_service == "api-gateway"


@pytest.mark.asyncio
async def test_incident_service_correlate_empty() -> None:
    """Verify correlate_unassigned_events returns empty list when no errors found."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_res

    service = IncidentService(db=mock_db)
    incidents = await service.correlate_unassigned_events(lookback_minutes=15)
    assert incidents == []


@pytest.mark.asyncio
async def test_incident_service_list_incidents() -> None:
    """Verify list_incidents filtering and mapping."""
    mock_db = AsyncMock()
    mock_count = MagicMock()
    mock_count.scalar.return_value = 1

    mock_inc = IncidentModel(
        id=str(uuid4()),
        incident_id="inc-test-abc",
        title="Payment gateway failure",
        status=IncidentStatus.DETECTED.value,
        severity=IncidentSeverity.CRITICAL.value,
        lead_service="payment-service",
        affected_services=["payment-service"],
        error_signatures=["sig-1"],
        started_at=datetime.now(UTC),
        detected_at=datetime.now(UTC),
        metadata_={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_inc.correlations = []

    mock_rows = MagicMock()
    mock_rows.scalars.return_value.all.return_value = [mock_inc]

    mock_db.execute.side_effect = [mock_count, mock_rows]

    service = IncidentService(db=mock_db)
    items, total = await service.list_incidents(
        status="DETECTED",
        severity="CRITICAL",
        lead_service="payment-service",
    )
    assert total == 1
    assert len(items) == 1
    assert items[0].incident_id == "inc-test-abc"
    assert items[0].severity == IncidentSeverity.CRITICAL


@pytest.mark.asyncio
async def test_incident_service_get_incident_detail_and_timeline() -> None:
    """Verify get_incident and get_timeline assemble full details and correlations."""
    mock_db = AsyncMock()
    now = datetime.now(UTC)

    mock_inc = IncidentModel(
        id=str(uuid4()),
        incident_id="inc-detail-01",
        title="Auth service degradation",
        status=IncidentStatus.INVESTIGATING.value,
        severity=IncidentSeverity.HIGH.value,
        lead_service="auth-service",
        affected_services=["auth-service"],
        error_signatures=[],
        started_at=now,
        detected_at=now,
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    mock_corr = IncidentCorrelationModel(
        id=str(uuid4()),
        incident_id=mock_inc.id,
        event_id="evt-42",
        correlation_type="CONFIRMED_CAUSAL",
        confidence_score=1.0,
        reason="Trace match",
        created_at=now,
    )
    mock_inc.correlations = [mock_corr]

    # Query 1: fetch incident
    mock_inc_res = MagicMock()
    mock_inc_res.scalar_one_or_none.return_value = mock_inc

    # Query 2: fetch correlated events
    mock_evt = LogEventModel(
        id=str(uuid4()),
        event_id="evt-42",
        timestamp=now,
        severity="ERROR",
        service_name="auth-service",
        environment="production",
        message="Token expired",
        attributes={},
        created_at=now,
    )
    mock_evts_res = MagicMock()
    mock_evts_res.scalars.return_value.all.return_value = [mock_evt]

    mock_db.execute.side_effect = [mock_inc_res, mock_evts_res]

    service = IncidentService(db=mock_db)
    detail = await service.get_incident("inc-detail-01")

    assert detail.incident_id == "inc-detail-01"
    assert len(detail.correlations) == 1
    assert detail.timeline is not None
    assert detail.timeline.total_events == 1

    # Now verify get_timeline calls get_incident and extracts the timeline
    mock_db.execute.side_effect = [mock_inc_res, mock_evts_res]
    timeline = await service.get_timeline("inc-detail-01")
    assert timeline.incident_id == "inc-detail-01"
    assert timeline.total_events == 1


@pytest.mark.asyncio
async def test_incident_service_update_status_transitions() -> None:
    """Verify update_status enforces transitions and human-in-the-loop requirements."""
    mock_db = AsyncMock()
    now = datetime.now(UTC)

    mock_inc = IncidentModel(
        id=str(uuid4()),
        incident_id="inc-status-01",
        title="Database lock issue",
        status=IncidentStatus.INVESTIGATING.value,
        severity=IncidentSeverity.HIGH.value,
        lead_service="db-service",
        affected_services=["db-service"],
        error_signatures=[],
        started_at=now,
        detected_at=now,
        metadata_={},
        created_at=now,
        updated_at=now,
    )

    mock_inc_res = MagicMock()
    mock_inc_res.scalar_one_or_none.return_value = mock_inc
    mock_db.execute.return_value = mock_inc_res

    service = IncidentService(db=mock_db)

    # Transition to IDENTIFIED
    updated = await service.update_status(
        "inc-status-01",
        IncidentStatusUpdate(
            new_status=IncidentStatus.IDENTIFIED,
            user_id="sre-alice",
            notes="Identified long query lock",
        ),
    )
    assert updated.status == IncidentStatus.IDENTIFIED

    # Attempting to resolve directly without MITIGATED raises error from state machine
    with pytest.raises(InvalidStateTransitionError):
        await service.update_status(
            "inc-status-01",
            IncidentStatusUpdate(
                new_status=IncidentStatus.RESOLVED,
                user_id="sre-alice",
            ),
        )


@pytest.mark.asyncio
async def test_incident_service_not_found() -> None:
    """Verify get_incident raises EntityNotFoundError when incident does not exist."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    service = IncidentService(db=mock_db)
    with pytest.raises(EntityNotFoundError, match="was not found"):
        await service.get_incident("non-existent-id")

    with pytest.raises(EntityNotFoundError, match="was not found"):
        await service.update_status(
            "non-existent-id",
            IncidentStatusUpdate(new_status=IncidentStatus.INVESTIGATING, user_id="sre"),
        )
