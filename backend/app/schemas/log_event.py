from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CanonicalLogEvent(BaseModel):
    """
    Production-grade canonical internal representation of an operational log entry.
    All ingestion pipelines must normalize source data into this exact structure.
    """

    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Globally unique identifier for the log event",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Normalized UTC ISO-8601 timestamp of event emission",
    )
    severity: Literal["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"] = Field(
        ...,
        description="Normalized log level",
    )
    service_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identifier of the emitting microservice or application",
    )
    environment: str = Field(
        default="production",
        description="Runtime environment: production, staging, dev",
    )
    message: str = Field(
        ...,
        description="Cleaned, primary log message text (PII scrubbed)",
    )
    exception_type: str | None = Field(
        default=None,
        description="Extracted class name of the exception if present",
    )
    stack_trace: str | None = Field(
        default=None,
        description="Full normalized multi-line stack trace",
    )
    error_signature: str | None = Field(
        default=None,
        description="SHA-256 hash of the normalized stack trace",
    )
    request_id: str | None = Field(
        default=None,
        description="HTTP or RPC request correlation identifier",
    )
    trace_id: str | None = Field(
        default=None,
        description="OpenTelemetry / W3C distributed trace identifier",
    )
    span_id: str | None = Field(
        default=None,
        description="OpenTelemetry span identifier",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Custom business transaction correlation ID",
    )
    source_file: str | None = Field(
        default=None,
        description="Source file name or uploaded artifact name",
    )
    line_number: int | None = Field(
        default=None,
        description="Source code line number if available",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured unindexed attributes",
    )
