"""Log parser factory with automatic format sniffing and instantiation."""

import re

from app.log_processing.parsers.base import BaseLogParser
from app.log_processing.parsers.docker_parser import DockerLogParser
from app.log_processing.parsers.java_parser import JavaLogParser
from app.log_processing.parsers.json_parser import JsonLogParser
from app.log_processing.parsers.nginx_parser import (
    NGINX_ACCESS_PATTERN,
    NGINX_ERROR_PATTERN,
    NginxLogParser,
)
from app.log_processing.parsers.python_parser import PythonLogParser


def detect_log_format(sample_lines: list[str]) -> str:
    """
    Sniff the log format based on a sample of lines from the beginning of the file.

    Returns:
        One of 'json', 'docker', 'nginx', 'java', 'python', 'generic'.
    """
    clean_lines = [line.strip() for line in sample_lines if line.strip()]
    if not clean_lines:
        return "generic"

    # 1. JSON check: if multiple lines start with { and end with }
    json_count = sum(1 for line in clean_lines if line.startswith("{") and line.endswith("}"))
    if json_count >= max(1, len(clean_lines) // 2):
        return "json"

    # 2. Docker container stream format
    docker_pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*\s+(?:stdout|stderr)\s+[FP]\s+"
    )
    if any(docker_pattern.match(line) for line in clean_lines):
        return "docker"

    # 3. Nginx access or error log check
    if any(
        NGINX_ACCESS_PATTERN.match(line) or NGINX_ERROR_PATTERN.match(line) for line in clean_lines
    ):
        return "nginx"

    # 4. Java Log4j / Logback check
    java_pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}.*\[[^\]]+\]\s+[A-Z]{3,8}\s+[a-zA-Z0-9_\.\$]+"
    )
    if any(java_pattern.match(line) or line.startswith("\tat ") for line in clean_lines):
        return "java"

    # 5. Python standard logging
    python_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}.*\[[A-Z]+\].*:")
    if any(python_pattern.match(line) for line in clean_lines):
        return "python"

    return "python"


def get_log_parser(
    format_hint: str | None = None,
    sample_lines: list[str] | None = None,
    service_name: str = "app-service",
    environment: str = "production",
) -> BaseLogParser:
    """
    Factory method to retrieve the appropriate parser instance.

    Args:
        format_hint: Explicit format requested by the user ('json', 'java', 'python', 'nginx', 'docker').
        sample_lines: Sample lines to sniff format if no hint is provided.
        service_name: Default emitting service name.
        environment: Deployment environment.

    Returns:
        Configured BaseLogParser instance.
    """
    fmt = (format_hint or "").strip().lower()
    if not fmt and sample_lines:
        fmt = detect_log_format(sample_lines)

    if fmt == "json":
        return JsonLogParser(service_name=service_name, environment=environment)
    if fmt == "docker":
        return DockerLogParser(service_name=service_name, environment=environment)
    if fmt == "nginx":
        return NginxLogParser(service_name=service_name, environment=environment)
    if fmt == "java":
        return JavaLogParser(service_name=service_name, environment=environment)

    # Default to PythonLogParser which handles standard timestamps, plain lines, and multi-line tracebacks
    return PythonLogParser(service_name=service_name, environment=environment)
