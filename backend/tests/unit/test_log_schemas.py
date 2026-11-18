"""Unit tests for CanonicalLogEvent and LogEventModel database representation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.log_event import LogEventModel
from app.schemas.log_event import CanonicalLogEvent


def test_canonical_log_event_defaults() -> None:
    """Verify default values on CanonicalLogEvent."""
    event = CanonicalLogEvent(
        severity="INFO",
        service_name="order-service",
        message="Order created successfully",
    )
    assert event.event_id is not None
    assert event.environment == "production"
    assert event.exception_type is None
    assert event.stack_trace is None
    assert event.error_signature is None
    assert event.metadata == {}
    assert event.timestamp.tzinfo is not None


def test_canonical_log_event_serialization_roundtrip() -> None:
    """Verify dictionary serialization and deserialization."""
    now = datetime.now(UTC)
    data = {
        "event_id": str(uuid4()),
        "timestamp": now.isoformat(),
        "severity": "ERROR",
        "service_name": "billing-service",
        "environment": "staging",
        "message": "Payment declined",
        "exception_type": "PaymentDeclinedException",
        "stack_trace": "Traceback:\n  line 1",
        "error_signature": "abcdef123456",
        "request_id": "req-123",
        "trace_id": "trace-456",
        "span_id": "span-789",
        "correlation_id": "corr-001",
        "source_file": "billing.log",
        "line_number": 42,
        "metadata": {"user_id": 99},
    }
    event = CanonicalLogEvent.model_validate(data)
    assert event.service_name == "billing-service"
    dumped = event.model_dump(mode="json")
    assert dumped["service_name"] == "billing-service"
    assert dumped["severity"] == "ERROR"


def test_canonical_log_event_validation_errors() -> None:
    """Ensure invalid severities and empty service names are rejected."""
    with pytest.raises(ValidationError):
        CanonicalLogEvent(severity="NON_EXISTENT", service_name="svc", message="msg")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        CanonicalLogEvent(severity="INFO", service_name="", message="msg")


def test_log_event_model_to_canonical() -> None:
    """Verify LogEventModel converts to CanonicalLogEvent correctly."""
    now = datetime.now(UTC)
    model = LogEventModel(
        id=str(uuid4()),
        event_id="evt-12345",
        timestamp=now,
        severity="WARN",
        service_name="cache-service",
        environment="production",
        message="Cache eviction threshold exceeded",
        exception_type=None,
        stack_trace=None,
        error_signature=None,
        request_id="req-555",
        trace_id=None,
        span_id=None,
        correlation_id=None,
        source_file="cache.log",
        line_number=None,
        attributes={"hit_ratio": 0.42},
        created_at=now,
    )
    canonical = model.to_canonical()
    assert canonical.event_id == "evt-12345"
    assert canonical.severity == "WARN"
    assert canonical.service_name == "cache-service"
    assert canonical.metadata == {"hit_ratio": 0.42}
