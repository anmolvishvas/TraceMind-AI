"""Unit tests for the multi-format log parser engine."""

from collections.abc import AsyncIterator

import pytest

from app.log_processing.parsers.base import normalize_severity, parse_timestamp
from app.log_processing.parsers.docker_parser import DockerLogParser
from app.log_processing.parsers.factory import detect_log_format, get_log_parser
from app.log_processing.parsers.java_parser import JavaLogParser
from app.log_processing.parsers.json_parser import JsonLogParser
from app.log_processing.parsers.nginx_parser import NginxLogParser
from app.log_processing.parsers.python_parser import PythonLogParser


def test_severity_and_timestamp_normalizers() -> None:
    """Test severity normalization and timestamp parsing edge cases."""
    assert normalize_severity("error") == "ERROR"
    assert normalize_severity("FATAL") == "CRITICAL"
    assert normalize_severity("warning") == "WARN"
    assert normalize_severity("NOTICE") == "INFO"
    assert normalize_severity(3) == "ERROR"
    assert normalize_severity(0) == "CRITICAL"
    assert normalize_severity(7) == "DEBUG"
    assert normalize_severity(None) == "INFO"

    ts_iso = parse_timestamp("2026-11-18T10:15:30.123Z")
    assert ts_iso.year == 2026
    assert ts_iso.hour == 10

    ts_epoch = parse_timestamp(1700000000)
    assert ts_epoch.year >= 2023

    ts_epoch_ms = parse_timestamp(1700000000000)
    assert ts_epoch_ms.year >= 2023


def test_json_log_parser() -> None:
    """Test JSON structured log parser with diverse schema variants."""
    parser = JsonLogParser(service_name="default-service")

    # Bunyan/Winston variant
    line1 = '{"time": "2026-11-18T10:00:00Z", "level": "error", "service": "auth-api", "msg": "Token expired", "reqId": "r-123"}'
    event1 = parser.parse_line(line1)
    assert event1 is not None
    assert event1.severity == "ERROR"
    assert event1.service_name == "auth-api"
    assert event1.message == "Token expired"
    assert event1.request_id == "r-123"

    # Zap/Structlog variant with error object
    line2 = '{"timestamp": "2026-11-18T10:05:00Z", "severity": "CRITICAL", "message": "DB dead", "error": {"name": "PoolExhausted", "stack": "PoolExhausted: all 50 conn in use"}}'
    event2 = parser.parse_line(line2)
    assert event2 is not None
    assert event2.severity == "CRITICAL"
    assert event2.exception_type == "PoolExhausted"
    assert event2.stack_trace == "PoolExhausted: all 50 conn in use"
    assert event2.error_signature is not None

    # Invalid JSON line returns None
    assert parser.parse_line("Not a JSON line") is None


def test_python_log_parser_and_traceback_stitching() -> None:
    """Test Python log parser and multi-line traceback collector."""
    parser = PythonLogParser(service_name="payment-service")

    log_stream = [
        "2026-11-18 10:15:30,123 [INFO] payment.worker: Processing transaction tx-99",
        "2026-11-18 10:15:31,456 [ERROR] payment.worker: Transaction failed",
        "Traceback (most recent call last):",
        '  File "/app/payment/worker.py", line 88, in process',
        "    gateway.charge(amount)",
        '  File "/app/payment/gateway.py", line 42, in charge',
        "    raise ConnectionRefusedError('Gateway port 8443 unreachable')",
        "ConnectionRefusedError: Gateway port 8443 unreachable",
        "2026-11-18 10:15:32,000 [INFO] payment.worker: Worker recovered",
    ]

    events = list(parser.parse_stream(iter(log_stream)))
    assert len(events) == 3

    assert events[0].severity == "INFO"
    assert "Processing transaction" in events[0].message

    assert events[1].severity == "ERROR"
    assert events[1].exception_type == "ConnectionRefusedError"
    assert events[1].stack_trace is not None
    assert "ConnectionRefusedError" in events[1].stack_trace
    assert events[1].error_signature is not None

    assert events[2].severity == "INFO"
    assert "Worker recovered" in events[2].message


def test_java_log_parser_and_stack_stitching() -> None:
    """Test Java Logback parser with multi-line stack trace stitching."""
    parser = JavaLogParser(service_name="order-service")

    log_stream = [
        "2026-11-18 10:20:00.000 [main] INFO com.example.order.Application - Started OrderApplication in 2.5 seconds",
        "2026-11-18 10:20:05.123 [http-nio-8080-exec-1] ERROR com.example.order.controller.OrderController - Failed to save order",
        "java.sql.SQLTimeoutException: Query execution timed out after 5000ms",
        "\tat com.zaxxer.hikari.pool.HikariProxyStatement.execute(HikariProxyStatement.java:137)",
        "\tat com.example.order.repository.OrderRepository.save(OrderRepository.java:55)",
        "\t... 30 common frames omitted",
        "2026-11-18 10:20:06.000 [main] INFO com.example.order.Application - Order controller ready",
    ]

    events = list(parser.parse_stream(iter(log_stream)))
    assert len(events) == 3

    assert events[0].severity == "INFO"
    assert events[1].severity == "ERROR"
    assert events[1].exception_type == "java.sql.SQLTimeoutException"
    assert events[1].stack_trace is not None
    assert "HikariProxyStatement" in events[1].stack_trace
    assert events[1].error_signature is not None
    assert events[2].severity == "INFO"


def test_nginx_log_parser() -> None:
    """Test Nginx access and error log parsing."""
    parser = NginxLogParser(service_name="nginx-gateway")

    # Access log 200 OK
    access_line = '192.168.1.100 - - [18/Nov/2026:10:30:00 +0000] "GET /api/v1/health HTTP/1.1" 200 64 "-" "curl/7.68.0"'
    event1 = parser.parse_line(access_line)
    assert event1 is not None
    assert event1.severity == "INFO"
    assert "HTTP 200" in event1.message
    assert event1.metadata["status_code"] == 200

    # Access log 500 Internal Error
    error_access = '10.0.0.5 - - [18/Nov/2026:10:30:05 +0000] "POST /api/v1/checkout HTTP/1.1" 500 128 "-" "PostmanRuntime/7.29"'
    event2 = parser.parse_line(error_access)
    assert event2 is not None
    assert event2.severity == "ERROR"

    # Error log
    error_line = "2026/11/18 10:30:10 [error] 1234#5678: *100 connect() failed (111: Connection refused) while connecting to upstream"
    event3 = parser.parse_line(error_line)
    assert event3 is not None
    assert event3.severity == "ERROR"
    assert "Connection refused" in event3.message


def test_docker_log_parser() -> None:
    """Test Docker container stream multiplexing and inner JSON unwrapping."""
    parser = DockerLogParser(service_name="docker-runner")

    # Plain Docker stdout
    line1 = "2026-11-18T10:35:00.000000000Z stdout F App initialized successfully"
    event1 = parser.parse_line(line1)
    assert event1 is not None
    assert event1.severity == "INFO"
    assert event1.message == "App initialized successfully"

    # Docker stderr with error keyword
    line2 = "2026-11-18T10:35:02.000000000Z stderr F [CRITICAL] Memory allocation error in thread 4"
    event2 = parser.parse_line(line2)
    assert event2 is not None
    assert event2.severity == "ERROR"

    # Docker stdout with nested JSON
    line3 = '2026-11-18T10:35:05.000000000Z stdout F {"level": "warn", "service": "cache-node", "msg": "Slow query detected"}'
    event3 = parser.parse_line(line3)
    assert event3 is not None
    assert event3.severity == "WARN"
    assert event3.service_name == "cache-node"
    assert event3.message == "Slow query detected"


def test_parser_factory_detection() -> None:
    """Verify log format sniffing in parser factory."""
    json_samples = ['{"timestamp": "2026-11-18T10:00:00Z", "level": "info", "msg": "hello"}']
    assert detect_log_format(json_samples) == "json"

    docker_samples = ["2026-11-18T10:00:00.000000000Z stdout F Started container"]
    assert detect_log_format(docker_samples) == "docker"

    nginx_samples = ['127.0.0.1 - - [18/Nov/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 40']
    assert detect_log_format(nginx_samples) == "nginx"

    java_samples = ["2026-11-18 10:00:00.000 [main] INFO com.example.App - Starting"]
    assert detect_log_format(java_samples) == "java"

    # Instantiation
    parser = get_log_parser(sample_lines=json_samples)
    assert isinstance(parser, JsonLogParser)
    assert isinstance(get_log_parser(format_hint="docker"), DockerLogParser)
    assert isinstance(get_log_parser(format_hint="java"), JavaLogParser)
    assert isinstance(get_log_parser(format_hint="nginx"), NginxLogParser)
    assert isinstance(get_log_parser(format_hint="python"), PythonLogParser)
    assert isinstance(get_log_parser(sample_lines=[]), PythonLogParser)


@pytest.mark.asyncio
async def test_python_log_parser_async_stream() -> None:
    """Verify parse_async_stream on PythonLogParser."""
    parser = PythonLogParser(service_name="async-service")

    async def async_lines() -> AsyncIterator[str]:
        lines = [
            "2026-11-18 10:15:30,123 [INFO] worker: Hello",
            "2026-11-18 10:15:31,456 [ERROR] worker: Failed",
            "Traceback (most recent call last):",
            "  File 'test.py', line 1, in <module>",
            "RuntimeError: Boom",
            "2026-11-18 10:15:32,000 [INFO] worker: Done",
        ]
        for line in lines:
            yield line

    events = [e async for e in parser.parse_async_stream(async_lines())]
    assert len(events) == 3
    assert events[1].exception_type == "RuntimeError"
    assert events[1].stack_trace is not None


@pytest.mark.asyncio
async def test_java_log_parser_async_stream() -> None:
    """Verify parse_async_stream on JavaLogParser."""
    parser = JavaLogParser(service_name="async-java")

    async def async_lines() -> AsyncIterator[str]:
        lines = [
            "2026-11-18 10:20:00.000 [main] INFO com.example.App - Ready",
            "2026-11-18 10:20:05.123 [main] ERROR com.example.App - Error in query",
            "java.lang.NullPointerException: Object is null",
            "\tat com.example.App.process(App.java:10)",
            "2026-11-18 10:20:06.000 [main] INFO com.example.App - Done",
        ]
        for line in lines:
            yield line

    events = [e async for e in parser.parse_async_stream(async_lines())]
    assert len(events) == 3
    assert events[1].exception_type == "java.lang.NullPointerException"


def test_json_parser_extended_fields() -> None:
    """Verify JSON parser extracts traceId, spanId, line_number, and nested error string."""
    parser = JsonLogParser(service_name="api")
    line = (
        '{"timestamp": "2026-11-18T10:00:00Z", "level": "warn", "message": "High latency", '
        '"trace_id": "tr-123", "span_id": "sp-456", "line_number": 42, '
        '"error": "TimeoutException: Call took 5s"}'
    )
    event = parser.parse_line(line)
    assert event is not None
    assert event.trace_id == "tr-123"
    assert event.span_id == "sp-456"
    assert event.line_number == 42
    assert event.exception_type == "TimeoutException"


def test_base_parser_stream_methods() -> None:
    """Test BaseLogParser stream iteration methods."""
    parser = JsonLogParser(service_name="stream-svc")
    lines = [
        '{"timestamp": "2026-11-18T10:00:00Z", "level": "info", "msg": "Event 1"}',
        "",
        '{"timestamp": "2026-11-18T10:00:01Z", "level": "info", "msg": "Event 2"}',
    ]
    events = list(parser.parse_stream(iter(lines), source_file="stream.log"))
    assert len(events) == 2


@pytest.mark.asyncio
async def test_base_parser_async_stream_method() -> None:
    """Test BaseLogParser async stream iteration."""
    parser = JsonLogParser(service_name="async-base-svc")

    async def gen_lines() -> AsyncIterator[str]:
        yield '{"timestamp": "2026-11-18T10:00:00Z", "level": "info", "msg": "Async 1"}'
        yield ""
        yield '{"timestamp": "2026-11-18T10:00:01Z", "level": "info", "msg": "Async 2"}'

    events = [e async for e in parser.parse_async_stream(gen_lines())]
    assert len(events) == 2


def test_docker_parser_edge_cases() -> None:
    """Test DockerLogParser handling direct JSON lines, invalid JSON, and non-error stderr."""
    parser = DockerLogParser(service_name="edge-docker")

    # Direct JSON line without docker prefix
    event_direct = parser.parse_line('{"msg": "Direct JSON", "level": "info"}')
    assert event_direct is not None
    assert event_direct.message == "Direct JSON"

    # Non-JSON plain line
    event_plain = parser.parse_line("Random non-docker string")
    assert event_plain is not None
    assert event_plain.message == "Random non-docker string"

    # Docker stderr without error keyword
    line_stderr = "2026-11-18T10:35:00.000Z stderr F Download progress 50%"
    event_stderr = parser.parse_line(line_stderr)
    assert event_stderr is not None
    assert event_stderr.severity == "WARN"

    # Docker stdout with invalid JSON
    line_bad_json = "2026-11-18T10:35:00.000Z stdout F {invalid json payload}"
    event_bad = parser.parse_line(line_bad_json)
    assert event_bad is not None
    assert "{invalid json payload}" in event_bad.message


def test_nginx_parser_fallback_line() -> None:
    """Verify fallback handling for non-matching Nginx log lines."""
    parser = NginxLogParser(service_name="nginx-edge")
    event = parser.parse_line("Non-standard Nginx raw line")
    assert event is not None
    assert event.message == "Non-standard Nginx raw line"
    assert event.severity == "INFO"
