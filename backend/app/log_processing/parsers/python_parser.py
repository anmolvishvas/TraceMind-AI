"""Parser for Python standard logging and multi-line tracebacks."""

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

# Regex for standard Python log line formats
PYTHON_LOG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,\.]\d{3,6})?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
    r"(?:\[(?P<level1>[A-Z]+)\]\s+)?(?:(?P<logger>[\w\.\-]+)(?:\s+-\s+|\s*:\s*))?"
    r"(?:\[(?P<level2>[A-Z]+)\]\s+)?(?P<message>.*)$"
)

TRACEBACK_START_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?:Traceback \(most recent call last\):|During handling of the above exception, another exception occurred:)"
)
EXCEPTION_LINE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<exc_type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning|Interrupt|Fault|Exit))(?::\s*(?P<exc_msg>.*))?$"
)


class PythonLogParser(BaseLogParser):
    """
    Parser for Python logging output with multi-line traceback stitching and exception classification.
    """

    def parse_line(self, line: str, source_file: str | None = None) -> CanonicalLogEvent | None:
        """Parse a single standalone Python log line."""
        clean = line.strip()
        match = PYTHON_LOG_PATTERN.match(clean)
        if not match:
            # Fallback to plain event
            return self.create_canonical_event(
                message=clean,
                severity="INFO",
                source_file=source_file,
            )

        groups = match.groupdict()
        timestamp = parse_timestamp(groups.get("timestamp"))
        raw_level = groups.get("level1") or groups.get("level2") or "INFO"
        severity: SeverityLevel = normalize_severity(raw_level)
        service = groups.get("logger") or self.default_service_name
        message = (groups.get("message") or "").strip()

        return self.create_canonical_event(
            message=message,
            severity=severity,
            timestamp=timestamp,
            service_name=service,
            source_file=source_file,
        )

    def parse_stream(
        self,
        lines: Iterator[str],
        source_file: str | None = None,
    ) -> Iterator[CanonicalLogEvent]:
        """
        Stream parser with a state machine to stitch multi-line Python tracebacks.
        """
        current_event: CanonicalLogEvent | None = None
        traceback_buffer: list[str] = []
        in_traceback = False

        for raw_line in lines:
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue

            # Check if this line is the start of a traceback
            if TRACEBACK_START_PATTERN.match(line):
                in_traceback = True
                traceback_buffer.append(line)
                continue

            # If inside traceback, check if it's a traceback frame or final exception line
            if in_traceback:
                if line.startswith("  ") or line.startswith("\t"):
                    traceback_buffer.append(line)
                    continue
                else:
                    # Final exception line (e.g. ValueError: Invalid user ID)
                    traceback_buffer.append(line)
                    in_traceback = False
                    exc_match = EXCEPTION_LINE_PATTERN.match(line)
                    exc_type = exc_match.group("exc_type") if exc_match else None

                    full_trace = "\n".join(traceback_buffer)
                    if current_event is not None:
                        # Attach traceback to the active event and set severity to ERROR if it was lower
                        updated_severity: SeverityLevel = (
                            "ERROR"
                            if current_event.severity in ("DEBUG", "INFO", "WARN")
                            else current_event.severity
                        )
                        current_event = self.create_canonical_event(
                            message=current_event.message,
                            severity=updated_severity,
                            timestamp=current_event.timestamp,
                            service_name=current_event.service_name,
                            environment=current_event.environment,
                            exception_type=exc_type or current_event.exception_type,
                            stack_trace=full_trace,
                            request_id=current_event.request_id,
                            trace_id=current_event.trace_id,
                            span_id=current_event.span_id,
                            correlation_id=current_event.correlation_id,
                            source_file=source_file or current_event.source_file,
                            line_number=current_event.line_number,
                            metadata=current_event.metadata,
                        )
                    else:
                        current_event = self.create_canonical_event(
                            message=line,
                            severity="ERROR",
                            exception_type=exc_type,
                            stack_trace=full_trace,
                            source_file=source_file,
                        )
                    traceback_buffer = []
                    continue

            # Check if this line starts a new log event
            match = PYTHON_LOG_PATTERN.match(line)
            if match:
                if current_event is not None:
                    yield current_event
                current_event = self.parse_line(line, source_file=source_file)
            else:
                # Continuation of previous message
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

        if current_event is not None:
            yield current_event

    async def parse_async_stream(
        self,
        lines: AsyncIterator[str],
        source_file: str | None = None,
    ) -> AsyncIterator[CanonicalLogEvent]:
        """Async streaming parser with traceback state machine."""
        current_event: CanonicalLogEvent | None = None
        traceback_buffer: list[str] = []
        in_traceback = False

        async for raw_line in lines:
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue

            if TRACEBACK_START_PATTERN.match(line):
                in_traceback = True
                traceback_buffer.append(line)
                continue

            if in_traceback:
                if line.startswith("  ") or line.startswith("\t"):
                    traceback_buffer.append(line)
                    continue
                else:
                    traceback_buffer.append(line)
                    in_traceback = False
                    exc_match = EXCEPTION_LINE_PATTERN.match(line)
                    exc_type = exc_match.group("exc_type") if exc_match else None
                    full_trace = "\n".join(traceback_buffer)

                    if current_event is not None:
                        updated_severity: SeverityLevel = (
                            "ERROR"
                            if current_event.severity in ("DEBUG", "INFO", "WARN")
                            else current_event.severity
                        )
                        current_event = self.create_canonical_event(
                            message=current_event.message,
                            severity=updated_severity,
                            timestamp=current_event.timestamp,
                            service_name=current_event.service_name,
                            environment=current_event.environment,
                            exception_type=exc_type or current_event.exception_type,
                            stack_trace=full_trace,
                            source_file=source_file or current_event.source_file,
                            metadata=current_event.metadata,
                        )
                    else:
                        current_event = self.create_canonical_event(
                            message=line,
                            severity="ERROR",
                            exception_type=exc_type,
                            stack_trace=full_trace,
                            source_file=source_file,
                        )
                    traceback_buffer = []
                    continue

            match = PYTHON_LOG_PATTERN.match(line)
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

        if current_event is not None:
            yield current_event
