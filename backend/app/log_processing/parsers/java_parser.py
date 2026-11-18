"""Parser for Java Log4j, Logback, and Spring Boot application logs with stack trace stitching."""

import re
from collections.abc import AsyncIterator, Iterator
from typing import Final

from app.log_processing.parsers.base import (
    BaseLogParser,
    SeverityLevel,
    normalize_severity,
    parse_timestamp,
)
from app.schemas.log_event import CanonicalLogEvent

JAVA_LOG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,\.]\d{3,6})?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
    r"(?:\[(?P<thread>[^\]]+)\]\s+)?"
    r"(?P<level>[A-Z]{3,8})\s+"
    r"(?P<logger>[a-zA-Z0-9_\.\$]+)\s+"
    r"(?:-\s+)?(?P<message>.*)$"
)

JAVA_STACK_FRAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?:at\s+|Caused by:\s+|org\.|com\.|java\.|javax\.|jakarta\.|net\.|io\.|[A-Za-z0-9_.]+(?:Exception|Error|Throwable)|(?:\.\.\.\s*\d+\s+more))"
)

JAVA_EXCEPTION_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?:Caused by:\s+)?(?P<exc_type>[a-zA-Z0-9_.]+(?:Exception|Error|Throwable|Fault))(?::\s*(?P<msg>.*))?$"
)


class JavaLogParser(BaseLogParser):
    """
    Parser for Java Spring Boot / Logback / Log4j application logs.
    Captures multi-line Java stack traces and extracts root cause exception classes.
    """

    def parse_line(self, line: str, source_file: str | None = None) -> CanonicalLogEvent | None:
        """Parse a single Java log line."""
        clean = line.strip()
        match = JAVA_LOG_PATTERN.match(clean)
        if not match:
            return self.create_canonical_event(
                message=clean,
                severity="INFO",
                source_file=source_file,
            )

        groups = match.groupdict()
        timestamp = parse_timestamp(groups.get("timestamp"))
        severity: SeverityLevel = normalize_severity(groups.get("level"))
        logger_name = groups.get("logger") or self.default_service_name
        message = (groups.get("message") or "").strip()
        thread_name = groups.get("thread")

        metadata = {}
        if thread_name:
            metadata["thread"] = thread_name
        if logger_name:
            metadata["logger"] = logger_name

        return self.create_canonical_event(
            message=message,
            severity=severity,
            timestamp=timestamp,
            service_name=logger_name.split(".")[-1] if "." in logger_name else logger_name,
            source_file=source_file,
            metadata=metadata,
        )

    def parse_stream(
        self,
        lines: Iterator[str],
        source_file: str | None = None,
    ) -> Iterator[CanonicalLogEvent]:
        """Stream parser with state machine to stitch multi-line Java stack traces."""
        current_event: CanonicalLogEvent | None = None
        stack_buffer: list[str] = []
        in_stack_trace = False

        for raw_line in lines:
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue

            # Check if this line is a stack frame or exception continuation
            if JAVA_STACK_FRAME_PATTERN.match(line.lstrip()):
                in_stack_trace = True
                stack_buffer.append(line)
                continue

            # If we were collecting a stack trace and reached a non-stack line
            if in_stack_trace and stack_buffer:
                in_stack_trace = False
                current_event = self._enrich_event_with_stack(current_event, stack_buffer)
                stack_buffer = []

            match = JAVA_LOG_PATTERN.match(line)
            if match:
                if current_event is not None:
                    yield current_event
                current_event = self.parse_line(line, source_file=source_file)
            else:
                if current_event is not None:
                    new_msg = f"{current_event.message}\n{line}"
                    current_event = self.create_canonical_event(
                        message=new_msg,
                        severity=current_event.severity,
                        timestamp=current_event.timestamp,
                        service_name=current_event.service_name,
                        environment=current_event.environment,
                        exception_type=current_event.exception_type,
                        stack_trace=current_event.stack_trace,
                        source_file=source_file,
                        metadata=current_event.metadata,
                    )
                else:
                    current_event = self.create_canonical_event(
                        message=line,
                        severity="INFO",
                        source_file=source_file,
                    )

        if in_stack_trace and stack_buffer and current_event is not None:
            current_event = self._enrich_event_with_stack(current_event, stack_buffer)

        if current_event is not None:
            yield current_event

    async def parse_async_stream(
        self,
        lines: AsyncIterator[str],
        source_file: str | None = None,
    ) -> AsyncIterator[CanonicalLogEvent]:
        """Asynchronously stream parsed Java logs."""
        current_event: CanonicalLogEvent | None = None
        stack_buffer: list[str] = []
        in_stack_trace = False

        async for raw_line in lines:
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue

            if JAVA_STACK_FRAME_PATTERN.match(line.lstrip()):
                in_stack_trace = True
                stack_buffer.append(line)
                continue

            if in_stack_trace and stack_buffer:
                in_stack_trace = False
                if current_event is not None:
                    current_event = self._enrich_event_with_stack(current_event, stack_buffer)
                stack_buffer = []

            match = JAVA_LOG_PATTERN.match(line)
            if match:
                if current_event is not None:
                    yield current_event
                current_event = self.parse_line(line, source_file=source_file)
            else:
                if current_event is not None:
                    new_msg = f"{current_event.message}\n{line}"
                    current_event = self.create_canonical_event(
                        message=new_msg,
                        severity=current_event.severity,
                        timestamp=current_event.timestamp,
                        service_name=current_event.service_name,
                        environment=current_event.environment,
                        exception_type=current_event.exception_type,
                        stack_trace=current_event.stack_trace,
                        source_file=source_file,
                        metadata=current_event.metadata,
                    )
                else:
                    current_event = self.create_canonical_event(
                        message=line,
                        severity="INFO",
                        source_file=source_file,
                    )

        if in_stack_trace and stack_buffer and current_event is not None:
            current_event = self._enrich_event_with_stack(current_event, stack_buffer)

        if current_event is not None:
            yield current_event

    def _enrich_event_with_stack(
        self,
        event: CanonicalLogEvent | None,
        frames: list[str],
    ) -> CanonicalLogEvent | None:
        """Helper to attach Java stack trace to the active event."""
        if event is None:
            return None

        full_trace = "\n".join(frames)
        exc_type = None

        # Look for exception type in frames
        for frame in frames:
            match = JAVA_EXCEPTION_NAME_PATTERN.match(frame.strip())
            if match:
                exc_type = match.group("exc_type")
                break

        updated_severity: SeverityLevel = (
            "ERROR" if event.severity in ("DEBUG", "INFO", "WARN") else event.severity
        )

        return self.create_canonical_event(
            message=event.message,
            severity=updated_severity,
            timestamp=event.timestamp,
            service_name=event.service_name,
            environment=event.environment,
            exception_type=exc_type or event.exception_type,
            stack_trace=full_trace,
            request_id=event.request_id,
            trace_id=event.trace_id,
            span_id=event.span_id,
            correlation_id=event.correlation_id,
            source_file=event.source_file,
            line_number=event.line_number,
            metadata=event.metadata,
        )
