"""Parser for Docker container log streams."""

import json
import re
from typing import Final

from app.log_processing.parsers.base import (
    BaseLogParser,
    SeverityLevel,
    parse_timestamp,
)
from app.log_processing.parsers.json_parser import JsonLogParser
from app.schemas.log_event import CanonicalLogEvent

DOCKER_LOG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s+"
    r"(?P<stream>stdout|stderr)\s+(?P<flag>[FP])\s+(?P<payload>.*)$"
)


class DockerLogParser(BaseLogParser):
    """
    Parser for Docker container log output. Unpacks container runtime stream headers
    and delegates nested JSON payloads to the JsonLogParser.
    """

    def __init__(self, service_name: str = "container", environment: str = "production") -> None:
        super().__init__(service_name=service_name, environment=environment)
        self._json_parser = JsonLogParser(service_name=service_name, environment=environment)

    def parse_line(self, line: str, source_file: str | None = None) -> CanonicalLogEvent | None:
        """Parse Docker log line with stream multiplexing."""
        clean = line.strip()
        match = DOCKER_LOG_PATTERN.match(clean)
        if not match:
            # If line starts directly with JSON, delegate to json_parser
            if clean.startswith("{") and clean.endswith("}"):
                return self._json_parser.parse_line(clean, source_file=source_file)
            return self.create_canonical_event(
                message=clean,
                severity="INFO",
                service_name=self.default_service_name,
                source_file=source_file,
            )

        data = match.groupdict()
        timestamp = parse_timestamp(data.get("timestamp"))
        stream = data.get("stream") or "stdout"
        payload = (data.get("payload") or "").strip()

        # If payload is JSON, delegate to JSON parser and override timestamp/stream
        if payload.startswith("{") and payload.endswith("}"):
            try:
                # Validate JSON syntax
                json.loads(payload)
                event = self._json_parser.parse_line(payload, source_file=source_file)
                if event is not None:
                    event.metadata["docker_stream"] = stream
                    return event
            except json.JSONDecodeError:
                pass

        severity: SeverityLevel = "WARN" if stream == "stderr" else "INFO"
        if (
            "error" in payload.lower()
            or "exception" in payload.lower()
            or "fatal" in payload.lower()
        ):
            severity = "ERROR"

        return self.create_canonical_event(
            message=payload,
            severity=severity,
            timestamp=timestamp,
            service_name=self.default_service_name,
            source_file=source_file,
            metadata={"docker_stream": stream},
        )
