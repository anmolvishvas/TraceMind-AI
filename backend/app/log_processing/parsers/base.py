"""Abstract base parser and parsing utilities for log ingestion."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Literal

from app.core.security import PIIScrubber
from app.log_processing.fingerprinter import ErrorFingerprinter
from app.schemas.log_event import CanonicalLogEvent

SeverityLevel = Literal["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]

SEVERITY_MAPPINGS: dict[str, SeverityLevel] = {
    "DEBUG": "DEBUG",
    "TRACE": "DEBUG",
    "FINE": "DEBUG",
    "FINER": "DEBUG",
    "FINEST": "DEBUG",
    "INFO": "INFO",
    "INFORMATIONAL": "INFO",
    "NOTICE": "INFO",
    "WARN": "WARN",
    "WARNING": "WARN",
    "ERROR": "ERROR",
    "ERR": "ERROR",
    "ERRO": "ERROR",
    "CRITICAL": "CRITICAL",
    "CRIT": "CRITICAL",
    "FATAL": "CRITICAL",
    "EMERGENCY": "CRITICAL",
    "ALERT": "CRITICAL",
    "PANIC": "CRITICAL",
}


def normalize_severity(raw_level: str | int | None) -> SeverityLevel:
    """Normalize any raw log level string or numeric syslog code to CanonicalLogEvent severity."""
    if raw_level is None:
        return "INFO"

    if isinstance(raw_level, int):
        # Syslog severity numbers (0=Emergency, 1=Alert, 2=Critical, 3=Error, 4=Warning, 5=Notice, 6=Info, 7=Debug)
        if raw_level <= 2:
            return "CRITICAL"
        if raw_level == 3:
            return "ERROR"
        if raw_level == 4:
            return "WARN"
        if raw_level in (5, 6):
            return "INFO"
        return "DEBUG"

    clean_str = str(raw_level).strip().upper()
    return SEVERITY_MAPPINGS.get(clean_str, "INFO")


def parse_timestamp(raw_ts: str | int | float | None) -> datetime:
    """
    Parse varied timestamp representations into a timezone-aware UTC datetime.
    Supports ISO-8601, Unix epoch (seconds/milliseconds), and common log formats.
    """
    if raw_ts is None:
        return datetime.now(UTC)

    if isinstance(raw_ts, (int, float)):
        # Check if milliseconds or seconds
        if raw_ts > 1e11:  # Milliseconds
            return datetime.fromtimestamp(raw_ts / 1000.0, tz=UTC)
        return datetime.fromtimestamp(float(raw_ts), tz=UTC)

    ts_str = str(raw_ts).strip()
    if not ts_str:
        return datetime.now(UTC)

    # Fast ISO parsing
    try:
        # Python 3.11+ handles Z and offsets
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        pass

    # Common log formats
    formats = [
        "%Y-%m-%d %H:%M:%S,%f",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%d/%b/%Y:%H:%M:%S %z",
        "%d/%b/%Y:%H:%M:%S",
        "%b %d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            continue

    return datetime.now(UTC)


class BaseLogParser(ABC):
    """Abstract interface defining log parsing contracts."""

    def __init__(self, service_name: str = "app-service", environment: str = "production") -> None:
        self.default_service_name = service_name
        self.default_environment = environment

    @abstractmethod
    def parse_line(self, line: str, source_file: str | None = None) -> CanonicalLogEvent | None:
        """Parse an individual log line."""

    def parse_stream(
        self,
        lines: Iterator[str],
        source_file: str | None = None,
    ) -> Iterator[CanonicalLogEvent]:
        """
        Synchronously parse an iterator of raw log lines.
        Subclasses may override this to handle multi-line stack trace stitching.
        """
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            event = self.parse_line(line_str, source_file=source_file)
            if event is not None:
                yield event

    async def parse_async_stream(
        self,
        lines: AsyncIterator[str],
        source_file: str | None = None,
    ) -> AsyncIterator[CanonicalLogEvent]:
        """Asynchronously stream parsed canonical log events."""
        async for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            event = self.parse_line(line_str, source_file=source_file)
            if event is not None:
                yield event

    def create_canonical_event(
        self,
        message: str,
        severity: SeverityLevel,
        timestamp: datetime | None = None,
        service_name: str | None = None,
        environment: str | None = None,
        exception_type: str | None = None,
        stack_trace: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        correlation_id: str | None = None,
        source_file: str | None = None,
        line_number: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> CanonicalLogEvent:
        """Helper to create and sanitize a canonical log event with deterministic fingerprinting."""
        scrubbed_message = PIIScrubber.scrub(message)
        scrubbed_trace = PIIScrubber.scrub(stack_trace) if stack_trace else None

        signature = None
        if severity in ("ERROR", "CRITICAL") or exception_type or scrubbed_trace:
            signature = ErrorFingerprinter.compute_signature(
                exception_type=exception_type,
                message=scrubbed_message,
                stack_trace=scrubbed_trace,
            )

        return CanonicalLogEvent(
            timestamp=timestamp or datetime.now(UTC),
            severity=severity,
            service_name=service_name or self.default_service_name,
            environment=environment or self.default_environment,
            message=scrubbed_message,
            exception_type=exception_type,
            stack_trace=scrubbed_trace,
            error_signature=signature,
            request_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
            correlation_id=correlation_id,
            source_file=source_file,
            line_number=line_number,
            metadata=metadata or {},
        )
