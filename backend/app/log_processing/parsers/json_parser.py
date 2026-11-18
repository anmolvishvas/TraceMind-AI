"""High-performance parser for structured JSON logs."""

import json
import logging
from typing import Any

from app.log_processing.parsers.base import BaseLogParser, normalize_severity, parse_timestamp
from app.schemas.log_event import CanonicalLogEvent

logger = logging.getLogger("tracemind.parsers.json")


class JsonLogParser(BaseLogParser):
    """
    Parser for JSON-formatted logs from Bunyan, Zap, Winston, Logstash, Structlog,
    and standard cloud logging agents.
    """

    def parse_line(self, line: str, source_file: str | None = None) -> CanonicalLogEvent | None:
        """Parse an individual JSON log line into CanonicalLogEvent."""
        clean_line = line.strip()
        if not (clean_line.startswith("{") and clean_line.endswith("}")):
            return None

        try:
            data: dict[str, Any] = json.loads(clean_line)
        except json.JSONDecodeError:
            return None

        # 1. Message extraction (check common keys)
        message = ""
        for msg_key in ("message", "msg", "log", "textPayload", "error_message", "detail"):
            if msg_key in data and data[msg_key]:
                message = str(data.pop(msg_key))
                break

        if not message:
            # Fallback if no explicit message key found
            message = json.dumps(data)

        # 2. Timestamp extraction
        raw_ts = None
        for ts_key in ("timestamp", "time", "ts", "@timestamp", "datetime", "created"):
            if ts_key in data:
                raw_ts = data.pop(ts_key)
                break
        timestamp = parse_timestamp(raw_ts)

        # 3. Severity extraction
        raw_level = None
        for lvl_key in ("level", "severity", "levelname", "log_level", "status"):
            if lvl_key in data:
                raw_level = data.pop(lvl_key)
                break
        severity = normalize_severity(raw_level)

        # 4. Service name extraction
        service = None
        for svc_key in ("service", "service_name", "app", "application", "component", "caller"):
            if svc_key in data and data[svc_key]:
                service = str(data.pop(svc_key))
                break

        # 5. Environment extraction
        env = None
        for env_key in ("environment", "env", "tier", "stage"):
            if env_key in data and data[env_key]:
                env = str(data.pop(env_key))
                break

        # 6. Exception and stack trace extraction
        exception_type = None
        stack_trace = None
        for err_key in ("stack_trace", "stack", "exception", "error", "traceback"):
            if err_key in data and data[err_key]:
                val = data.pop(err_key)
                if isinstance(val, dict):
                    exception_type = str(val.get("name") or val.get("type") or "Exception")
                    stack_trace = str(val.get("stack") or val.get("message") or "")
                elif isinstance(val, str):
                    stack_trace = val
                    # Extract exception class name from first line if possible
                    first_line = val.strip().splitlines()[0]
                    if ":" in first_line:
                        exception_type = first_line.split(":")[0].strip()
                break

        # 7. Tracing & Correlation IDs
        trace_id = None
        for tr_key in ("trace_id", "traceId", "trace", "logging.googleapis.com/trace"):
            if tr_key in data and data[tr_key]:
                trace_id = str(data.pop(tr_key))
                break

        span_id = None
        for sp_key in ("span_id", "spanId", "span", "logging.googleapis.com/spanId"):
            if sp_key in data and data[sp_key]:
                span_id = str(data.pop(sp_key))
                break

        request_id = None
        for req_key in ("request_id", "requestId", "reqId", "x-request-id"):
            if req_key in data and data[req_key]:
                request_id = str(data.pop(req_key))
                break

        correlation_id = None
        for cor_key in ("correlation_id", "correlationId", "x-correlation-id"):
            if cor_key in data and data[cor_key]:
                correlation_id = str(data.pop(cor_key))
                break

        # 8. Source file & line
        line_num = None
        if "line" in data and isinstance(data["line"], int):
            line_num = data.pop("line")
        elif "line_number" in data and isinstance(data["line_number"], int):
            line_num = data.pop("line_number")

        return self.create_canonical_event(
            message=message,
            severity=severity,
            timestamp=timestamp,
            service_name=service,
            environment=env,
            exception_type=exception_type,
            stack_trace=stack_trace,
            request_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
            correlation_id=correlation_id,
            source_file=source_file,
            line_number=line_num,
            metadata=data,
        )
