"""SQLAlchemy 2.0 declarative model for persisted operational log events."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base
from app.schemas.log_event import CanonicalLogEvent


class LogEventModel(Base):
    """
    Persisted log event record mapped to the 'log_events' relational table.
    Configured with composite indexes optimized for time-series filtering and incident correlation.
    """

    __tablename__ = "log_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        doc="Internal primary key UUID",
    )
    event_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        doc="Canonical event UUID",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        doc="Normalized UTC timestamp of log occurrence",
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        index=True,
        nullable=False,
        doc="Normalized log level (DEBUG, INFO, WARN, ERROR, CRITICAL)",
    )
    service_name: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        doc="Emitting service identifier",
    )
    environment: Mapped[str] = mapped_column(
        String(32),
        default="production",
        index=True,
        nullable=False,
        doc="Deployment tier (production, staging, dev)",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Sanitized log message",
    )
    exception_type: Mapped[str | None] = mapped_column(
        String(256),
        index=True,
        nullable=True,
        doc="Extracted exception class name",
    )
    stack_trace: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Normalized multi-line stack trace",
    )
    error_signature: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
        nullable=True,
        doc="Deterministic SHA-256 fingerprint",
    )
    request_id: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
        nullable=True,
        doc="Correlation request identifier",
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
        nullable=True,
        doc="W3C/OpenTelemetry distributed trace ID",
    )
    span_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="OpenTelemetry span ID",
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
        nullable=True,
        doc="Business transaction correlation ID",
    )
    source_file: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        doc="Source file name or uploaded file",
    )
    line_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Source code line number",
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=False,
        doc="Arbitrary structured metadata",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        doc="Record creation timestamp in TraceMind",
    )

    __table_args__ = (
        Index("ix_log_events_service_timestamp", "service_name", "timestamp"),
        Index("ix_log_events_signature_timestamp", "error_signature", "timestamp"),
        Index("ix_log_events_severity_timestamp", "severity", "timestamp"),
        Index("ix_log_events_env_service", "environment", "service_name"),
    )

    def to_canonical(self) -> CanonicalLogEvent:
        """Convert database entity to canonical Pydantic model."""
        return CanonicalLogEvent(
            event_id=self.event_id,
            timestamp=self.timestamp,
            severity=self.severity,  # type: ignore[arg-type]
            service_name=self.service_name,
            environment=self.environment,
            message=self.message,
            exception_type=self.exception_type,
            stack_trace=self.stack_trace,
            error_signature=self.error_signature,
            request_id=self.request_id,
            trace_id=self.trace_id,
            span_id=self.span_id,
            correlation_id=self.correlation_id,
            source_file=self.source_file,
            line_number=self.line_number,
            metadata=self.attributes,
        )
