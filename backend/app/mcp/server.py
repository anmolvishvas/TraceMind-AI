"""Model Context Protocol (MCP) server for TraceMind AI incident intelligence."""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from mcp.server.mcpserver import MCPServer

from app.mcp import tools

logger = logging.getLogger("tracemind.mcp.server")

# Instantiate official MCP Server
mcp_server = MCPServer(
    name="TraceMind AI",
    instructions=(
        "TraceMind AI incident intelligence platform exposing read-only operational telemetry, "
        "statistical anomaly detection, incident correlations, and evidence-grounded root cause analyses."
    ),
)


# Register all 10 official tools
@mcp_server.tool()
async def search_logs(
    query: str,
    service_name: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Search operational application logs by text query, service name, or severity level."""
    return await tools.mcp_search_logs(
        query=query,
        service_name=service_name,
        severity=severity,
        limit=limit,
        auth_token=auth_token,
    )


@mcp_server.tool()
async def get_log_details(
    event_id: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Retrieve full details, stack trace, and metadata for a specific log event."""
    return await tools.mcp_get_log_details(event_id=event_id, auth_token=auth_token)


@mcp_server.tool()
async def analyse_error_pattern(
    service_name: str | None = None,
    lookback_minutes: int = 60,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Analyze error patterns and group recurring exceptions by deterministic error signatures."""
    return await tools.mcp_analyse_error_pattern(
        service_name=service_name,
        lookback_minutes=lookback_minutes,
        auth_token=auth_token,
    )


@mcp_server.tool()
async def detect_anomalies(
    service_name: str,
    metric_name: str = "error_rate",
    method: str = "Z_SCORE",
    sensitivity: float = 1.0,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Execute pure Python statistical anomaly detection over recent service telemetry."""
    return await tools.mcp_detect_anomalies(
        service_name=service_name,
        metric_name=metric_name,
        method=method,
        sensitivity=sensitivity,
        auth_token=auth_token,
    )


@mcp_server.tool()
async def get_incident_details(
    incident_id: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Retrieve incident status, blast radius, severity, and correlated events."""
    return await tools.mcp_get_incident_details(incident_id=incident_id, auth_token=auth_token)


@mcp_server.tool()
async def get_incident_timeline(
    incident_id: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Retrieve strictly ordered progression milestones for an incident timeline."""
    return await tools.mcp_get_incident_timeline(incident_id=incident_id, auth_token=auth_token)


@mcp_server.tool()
async def find_related_incidents(
    service_name: str,
    lookback_days: int = 30,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Find past or co-occurring incidents involving the specified service."""
    return await tools.mcp_find_related_incidents(
        service_name=service_name,
        lookback_days=lookback_days,
        auth_token=auth_token,
    )


@mcp_server.tool()
async def search_historical_incidents(
    query: str,
    limit: int = 5,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Semantic vector search against historical post-mortems and operational runbooks."""
    return await tools.mcp_search_historical_incidents(
        query=query,
        limit=limit,
        auth_token=auth_token,
    )


@mcp_server.tool()
async def get_service_health(
    service_name: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Assess service operational health from active incidents, error rates, and anomalies."""
    return await tools.mcp_get_service_health(service_name=service_name, auth_token=auth_token)


@mcp_server.tool()
async def generate_incident_report(
    incident_id: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Generate an evidence-grounded AI Root Cause Analysis (RCA) report for an incident."""
    return await tools.mcp_generate_incident_report(
        incident_id=incident_id,
        auth_token=auth_token,
    )


def create_mcp_server() -> MCPServer:
    """Return configured MCPServer instance."""
    return mcp_server


def main() -> None:
    """CLI Entrypoint for running the TraceMind MCP server."""
    parser = argparse.ArgumentParser(description="TraceMind AI MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport protocol (stdio or sse)",
    )
    parser.add_argument("--port", type=int, default=8001, help="Port for SSE transport")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger.info("Starting TraceMind AI MCP server on transport '%s'...", args.transport)

    if args.transport == "stdio":
        asyncio.run(mcp_server.run_stdio_async())
    elif args.transport == "sse":
        asyncio.run(mcp_server.run_sse_async())


if __name__ == "__main__":
    main()
