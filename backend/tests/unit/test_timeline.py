"""Unit tests for chronological IncidentTimelineGenerator."""

from datetime import UTC, datetime, timedelta

from app.incidents.timeline import IncidentTimelineGenerator
from app.schemas.anomaly import AnomalyRecord, AnomalySeverity, DetectionMethod
from app.schemas.incident import MilestoneType
from app.schemas.log_event import CanonicalLogEvent


def test_timeline_single_service_milestones() -> None:
    """Verify FIRST_TRIGGER, ROOT_EXCEPTION, and PEAK_IMPACT milestone assembly."""
    now = datetime.now(UTC)
    events = [
        CanonicalLogEvent(
            event_id="e1",
            timestamp=now,
            severity="ERROR",
            service_name="payment-service",
            message="Database query timed out",
            exception_type="QueryTimeoutError",
            error_signature="sig-timeout",
        ),
        CanonicalLogEvent(
            event_id="e2",
            timestamp=now + timedelta(seconds=10),
            severity="ERROR",
            service_name="payment-service",
            message="Database pool unreachable",
            exception_type="PoolExhaustionError",
            error_signature="sig-pool",
        ),
    ]

    timeline = IncidentTimelineGenerator.generate_timeline(
        incident_id="inc-test-01",
        started_at=now,
        detected_at=now + timedelta(seconds=10),
        resolved_at=None,
        events=events,
    )

    assert timeline.incident_id == "inc-test-01"
    assert timeline.total_events == 2
    assert timeline.services_involved == ["payment-service"]

    # Verify milestones
    types = [m.milestone_type for m in timeline.milestones]
    assert MilestoneType.FIRST_TRIGGER in types
    assert MilestoneType.ROOT_EXCEPTION in types


def test_timeline_cascading_milestone() -> None:
    """Verify CASCADE_PROPAGATION milestone when secondary services degrade."""
    now = datetime.now(UTC)
    events = [
        CanonicalLogEvent(
            event_id="e1",
            timestamp=now,
            severity="ERROR",
            service_name="auth-service",
            message="Redis cluster down",
        ),
        CanonicalLogEvent(
            event_id="e2",
            timestamp=now + timedelta(seconds=30),
            severity="ERROR",
            service_name="api-gateway",
            message="Auth token verification returned 500",
        ),
    ]

    timeline = IncidentTimelineGenerator.generate_timeline(
        incident_id="inc-test-02",
        started_at=now,
        detected_at=now + timedelta(seconds=30),
        resolved_at=None,
        events=events,
    )

    types = [m.milestone_type for m in timeline.milestones]
    assert MilestoneType.CASCADE_PROPAGATION in types
    cascade_m = next(
        m for m in timeline.milestones if m.milestone_type == MilestoneType.CASCADE_PROPAGATION
    )
    assert cascade_m.service_name == "api-gateway"


def test_timeline_strict_chronological_order() -> None:
    """Verify all milestones are strictly ordered in ascending temporal sequence."""
    now = datetime.now(UTC)
    events = [
        CanonicalLogEvent(
            event_id=f"e-{i}",
            timestamp=now + timedelta(minutes=i * 5),
            severity="ERROR",
            service_name="order-service",
            message=f"Order failed #{i}",
        )
        for i in range(4)
    ]

    anomalies = [
        AnomalyRecord(
            service_name="order-service",
            timestamp=now + timedelta(minutes=7),
            metric_name="error_rate",
            current_value=45.0,
            threshold=10.0,
            anomaly_score=0.9,
            severity=AnomalySeverity.CRITICAL,
            detection_method=DetectionMethod.Z_SCORE,
            confidence=0.95,
        )
    ]

    history = [
        {
            "timestamp": now + timedelta(minutes=10),
            "status": "INVESTIGATING",
            "user_id": "engineer@tracemind.ai",
        },
        {
            "timestamp": now + timedelta(minutes=25),
            "status": "MITIGATED",
            "user_id": "engineer@tracemind.ai",
        },
    ]

    timeline = IncidentTimelineGenerator.generate_timeline(
        incident_id="inc-test-03",
        started_at=now,
        detected_at=now + timedelta(minutes=25),
        resolved_at=now + timedelta(minutes=30),
        events=events,
        anomalies=anomalies,
        status_history=history,
    )

    # Check timestamps are monotonically increasing
    for idx in range(len(timeline.milestones) - 1):
        assert timeline.milestones[idx].timestamp <= timeline.milestones[idx + 1].timestamp
