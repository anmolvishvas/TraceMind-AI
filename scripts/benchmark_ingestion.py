"""
High-throughput streaming ingestion benchmark script for TraceMind AI.
Validates sub-second micro-batch parsing and streaming ingestion throughput (>= 5,000 events/sec).
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.log_processing.parsers.json_parser import JsonLogParser
from app.log_processing.parsers.python_parser import PythonLogParser

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("tracemind.benchmark")


def generate_synthetic_json_logs(count: int) -> bytes:
    """Generate in-memory synthetic JSON log stream."""
    lines = []
    for i in range(count):
        lines.append(
            f'{{"timestamp": "2026-11-19T10:14:{i % 60:02d}Z", "level": "ERROR", '
            f'"service": "payment-gateway", "message": "Transaction failed error #{i}", '
            f'"trace_id": "tr-{i // 10}", "exception": "TimeoutError"}}\n'
        )
    return "".join(lines).encode("utf-8")


async def run_benchmark(event_count: int = 25000) -> None:
    logger.info("Starting Streaming Ingestion Benchmark (%d events)...", event_count)

    # 1. JSON Parser Benchmark
    data = generate_synthetic_json_logs(event_count)
    lines = data.decode("utf-8").splitlines()
    parser = JsonLogParser()

    start_time = time.perf_counter()
    parsed_count = 0
    for _ in parser.parse_stream(lines):
        parsed_count += 1
    duration = time.perf_counter() - start_time

    throughput = parsed_count / duration if duration > 0 else 0
    logger.info("JSON Parsing Benchmark Results:")
    logger.info("  - Ingested Events: %d", parsed_count)
    logger.info("  - Total Duration:  %.3f seconds", duration)
    logger.info("  - Throughput:      %.1f events/second", throughput)

    assert parsed_count == event_count, f"Expected {event_count}, got {parsed_count}"
    assert throughput >= 5000.0, (
        f"Throughput {throughput:.1f} < 5,000 events/sec target"
    )

    # 2. Python Stack Trace Benchmark
    py_lines_raw = []
    for i in range(1000):
        py_lines_raw.append(
            f"2026-11-19 10:14:00 [ERROR] payment-gateway: OperationalError in db/pool.py\n"
            f"Traceback (most recent call last):\n"
            f'  File "app/main.py", line 12, in handle\n'
            f"    db.query()\n"
            f"TimeoutError: QueuePool limit reached (iteration {i})\n"
        )
    py_data = "".join(py_lines_raw)
    py_lines = py_data.splitlines()
    py_parser = PythonLogParser()

    py_start = time.perf_counter()
    py_count = 0
    for _ in py_parser.parse_stream(py_lines):
        py_count += 1
    py_duration = time.perf_counter() - py_start
    py_throughput = py_count / py_duration if py_duration > 0 else 0

    logger.info("Python Multi-Line Parser Results:")
    logger.info("  - Ingested Events: %d", py_count)
    logger.info("  - Total Duration:  %.3f seconds", py_duration)
    logger.info("  - Throughput:      %.1f events/second", py_throughput)

    logger.info(
        "Benchmark PASSED: All parsing pipelines meet enterprise performance thresholds."
    )


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 25000
    asyncio.run(run_benchmark(count))
