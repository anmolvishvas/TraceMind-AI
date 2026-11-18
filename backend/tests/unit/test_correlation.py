"""Unit tests for multi-dimensional IncidentCorrelator."""

from datetime import UTC, datetime, timedelta

from app.incidents.correlator import IncidentCorrelator
from app.schemas.incident import CorrelationType
from app.schemas.log_event import CanonicalLogEvent


def test_correlate_empty_events() -> None:
    """Verify empty input produces zero incident candidates."""
    correlator = IncidentCorrelator()
    clusters = correlator.correlate_events([])
    assert clusters == []


def test_correlate_filters_non_errors() -> None:
    """Verify INFO and DEBUG logs without exceptions are ignored."""
    correlator = IncidentCorrelator()
    events = [
        CanonicalLogEvent(
            event_id="e1",
            timestamp=datetime.now(UTC),
            severity="INFO",
            service_name="api",
            message="Health check ok",
        ),
        CanonicalLogEvent(
            event_id="e2",
            timestamp=datetime.now(UTC),
            severity="DEBUG",
            service_name="api",
            message="Cache hit",
        ),
    ]
    clusters = correlator.correlate_events(events)
    assert clusters == []


def test_correlate_trace_id_confirmed_causal() -> None:
    """Verify events sharing trace_id across microservices form CONFIRMED_CAUSAL incident."""
    correlator = IncidentCorrelator()
    now = datetime.now(UTC)
    trace_id = "trace-distributed-abc-123"

    events = [
        CanonicalLogEvent(
            event_id="e1",
            timestamp=now,
            severity="ERROR",
            service_name="api-gateway",
            message="HTTP 502 Bad Gateway from upstream payment",
            trace_id=trace_id,
        ),
        CanonicalLogEvent(
            event_id="e2",
            timestamp=now + timedelta(seconds=2),
            severity="ERROR",
            service_name="payment-service",
            message="Database connection pool timeout",
            exception_type="ConnectionTimeoutError",
            trace_id=trace_id,
        ),
    ]

    clusters = correlator.correlate_events(events)
    assert len(clusters) == 1
    incident, correlations = clusters[0]

    assert incident.lead_service == "api-gateway"
    assert incident.affected_services == ["api-gateway", "payment-service"]
    assert len(correlations) == 2
    assert all(c.correlation_type == CorrelationType.CONFIRMED_CAUSAL for c in correlations)
    assert all(c.confidence_score == 1.0 for c in correlations)


def test_correlate_signature_burst() -> None:
    """Verify burst of matching error signature forms SIGNATURE_BURST incident."""
    correlator = IncidentCorrelator(temporal_window_seconds=300)
    now = datetime.now(UTC)
    sig = "sha256-sig-999"

    events = [
        CanonicalLogEvent(
            event_id=f"e-{i}",
            timestamp=now + timedelta(seconds=i * 10),
            severity="ERROR",
            service_name="auth-service",
            message=f"JWT verification failed token #{i}",
            error_signature=sig,
        )
        for i in range(5)
    ]

    clusters = correlator.correlate_events(events)
    assert len(clusters) == 1
    incident, correlations = clusters[0]

    assert incident.lead_service == "auth-service"
    assert incident.error_signatures == [sig]
    assert all(c.correlation_type == CorrelationType.SIGNATURE_BURST for c in correlations)


def test_correlate_cascading_failure_topology() -> None:
    """Verify related services failing within temporal window are clustered as CASCADING_FAILURE."""
    correlator = IncidentCorrelator(temporal_window_seconds=300)
    now = datetime.now(UTC)

    events = [
        CanonicalLogEvent(
            event_id="e1",
            timestamp=now,
            severity="ERROR",
            service_name="payment-service",
            message="Postgres pool exhausted",
            exception_type="PoolTimeout",
        ),
        CanonicalLogEvent(
            event_id="e2",
            timestamp=now + timedelta(seconds=15),
            severity="ERROR",
            service_name="order-service",
            message="Payment call failed during checkout",
        ),
    ]

    clusters = correlator.correlate_events(events)
    assert len(clusters) == 1
    incident, correlations = clusters[0]

    assert incident.lead_service == "payment-service"
    assert "order-service" in incident.affected_services
    assert all(c.correlation_type == CorrelationType.CASCADING_FAILURE for c in correlations)
