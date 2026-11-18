"""Parser for Nginx access and error logs."""

import re
from typing import Final

from app.log_processing.parsers.base import (
    BaseLogParser,
    SeverityLevel,
    normalize_severity,
    parse_timestamp,
)
from app.schemas.log_event import CanonicalLogEvent

# Combined Access Log format
NGINX_ACCESS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r'^(?P<client_ip>\S+)\s+\S+\s+(?P<user>\S+)\s+\[(?P<timestamp>[^\]]+)\]\s+"(?P<request>[^"]*)"\s+'
    r'(?P<status>\d{3})\s+(?P<bytes>\S+)(?:\s+"(?P<referrer>[^"]*)"\s+"(?P<user_agent>[^"]*)")?'
)

# Nginx Error Log format
NGINX_ERROR_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<timestamp>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\s+\[(?P<level>[a-z]+)\]\s+"
    r"(?P<pid>\d+)#(?P<tid>\d+):\s+(?:\*(?P<cid>\d+)\s+)?(?P<message>.*)$"
)


class NginxLogParser(BaseLogParser):
    """
    Parser for Nginx web server access logs and error logs.
    """

    def __init__(self, service_name: str = "nginx", environment: str = "production") -> None:
        super().__init__(service_name=service_name, environment=environment)

    def parse_line(self, line: str, source_file: str | None = None) -> CanonicalLogEvent | None:
        """Parse an individual Nginx access or error log entry."""
        clean = line.strip()

        # Check access log first
        access_match = NGINX_ACCESS_PATTERN.match(clean)
        if access_match:
            data = access_match.groupdict()
            timestamp = parse_timestamp(data.get("timestamp"))
            status_code = int(data.get("status") or 200)

            severity: SeverityLevel = "INFO"
            if status_code >= 500:
                severity = "ERROR"
            elif status_code >= 400:
                severity = "WARN"

            request = data.get("request") or ""
            message = f"{request} -> HTTP {status_code}"

            metadata = {
                "client_ip": data.get("client_ip"),
                "status_code": status_code,
                "bytes_sent": data.get("bytes"),
                "request": request,
                "user_agent": data.get("user_agent"),
                "referrer": data.get("referrer"),
            }

            return self.create_canonical_event(
                message=message,
                severity=severity,
                timestamp=timestamp,
                service_name=self.default_service_name,
                source_file=source_file,
                metadata=metadata,
            )

        # Check error log
        error_match = NGINX_ERROR_PATTERN.match(clean)
        if error_match:
            data = error_match.groupdict()
            timestamp = parse_timestamp(data.get("timestamp"))
            raw_level = data.get("level") or "error"
            severity = normalize_severity(raw_level)
            message = data.get("message") or clean

            metadata = {
                "pid": data.get("pid"),
                "tid": data.get("tid"),
                "connection_id": data.get("cid"),
            }

            return self.create_canonical_event(
                message=message,
                severity=severity,
                timestamp=timestamp,
                service_name=self.default_service_name,
                source_file=source_file,
                metadata=metadata,
            )

        # Fallback
        return self.create_canonical_event(
            message=clean,
            severity="INFO",
            service_name=self.default_service_name,
            source_file=source_file,
        )
