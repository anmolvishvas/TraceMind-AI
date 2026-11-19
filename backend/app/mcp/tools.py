"""Strongly typed tool implementations for the TraceMind Model Context Protocol (MCP) server."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy import func, select

from app.core.database import async_session_maker
from app.core.exceptions import EntityNotFoundError
from app.mcp.auth import MCPAuthenticator
from app.models.incident import IncidentModel
from app.models.log_event import LogEventModel
from app.schemas.anomaly import AnomalyDetectionRequest, DetectionMethod, MetricDataPoint
from app.schemas.rag import SemanticSearchRequest
from app.schemas.rca import RCARequest
from app.services.anomaly_service import AnomalyService
from app.services.incident_service import IncidentService
from app.services.log_service import LogService
from app.services.rag_service import RAGService
from app.services.rca_service import RCAService

logger = logging.getLogger("tracemind.mcp.tools")
authenticator = MCPAuthenticator()


# 1. search_logs
async def mcp_search_logs(
    query: str,
    service_name: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Search operational application logs by text query, service name, or severity level.
    """
    authenticator.authorize_read_access(auth_token)
    async with async_session_maker() as db:
        service = LogService(db=db)
        events, total = await service.search_logs(
            query=query,
            service_name=service_name,
            severity=severity,
            limit=min(limit, 100),
        )
        return {
            "total_matches": total,
            "returned_count": len(events),
            "events": [e.model_dump() for e in events],
        }


# 2. get_log_details
async def mcp_get_log_details(
    event_id: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve exhaustive details, stack trace, and metadata for a specific log event.
    """
    authenticator.authorize_read_access(auth_token)
    async with async_session_maker() as db:
        service = LogService(db=db)
        event = await service.get_by_event_id(event_id)
        if event is None:
            return {"error": f"Log event '{event_id}' was not found.", "status": "NOT_FOUND"}
        return {"event": event.model_dump()}


# 3. analyse_error_pattern
async def mcp_analyse_error_pattern(
    service_name: str | None = None,
    lookback_minutes: int = 60,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Analyze error patterns and group recurring exceptions by deterministic error signatures.
    """
    authenticator.authorize_read_access(auth_token)
    cutoff = datetime.now(UTC) - timedelta(minutes=lookback_minutes)
    async with async_session_maker() as db:
        stmt = (
            select(
                LogEventModel.error_signature,
                LogEventModel.service_name,
                LogEventModel.exception_type,
                func.count(LogEventModel.id).label("occurrence_count"),
                func.min(LogEventModel.timestamp).label("first_seen"),
                func.max(LogEventModel.timestamp).label("last_seen"),
            )
            .where(
                LogEventModel.timestamp >= cutoff,
                LogEventModel.severity.in_(["ERROR", "CRITICAL"]),
                LogEventModel.error_signature.is_not(None),
            )
            .group_by(
                LogEventModel.error_signature,
                LogEventModel.service_name,
                LogEventModel.exception_type,
            )
            .order_by(sa.desc("occurrence_count"))
            .limit(20)
        )
        if service_name:
            stmt = stmt.where(LogEventModel.service_name == service_name)

        res = await db.execute(stmt)
        patterns = [
            {
                "error_signature": row.error_signature,
                "service_name": row.service_name,
                "exception_type": row.exception_type or "UnknownException",
                "occurrence_count": row.occurrence_count,
                "first_seen": row.first_seen.isoformat() if row.first_seen else None,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
            for row in res.all()
        ]
        return {
            "lookback_minutes": lookback_minutes,
            "service_name": service_name,
            "total_patterns": len(patterns),
            "patterns": patterns,
        }


# 4. detect_anomalies
async def mcp_detect_anomalies(
    service_name: str,
    metric_name: str = "error_rate",
    method: str = "Z_SCORE",
    sensitivity: float = 1.0,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Execute pure Python statistical anomaly detection over recent service telemetry.
    """
    authenticator.authorize_read_access(auth_token)
    async with async_session_maker() as db:
        # Fetch recent error count buckets
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=2)
        stmt = (
            select(
                func.date_trunc("minute", LogEventModel.timestamp).label("bucket"),
                func.count(LogEventModel.id).label("error_count"),
            )
            .where(
                LogEventModel.service_name == service_name,
                LogEventModel.timestamp >= cutoff,
                LogEventModel.severity.in_(["ERROR", "CRITICAL"]),
            )
            .group_by("bucket")
            .order_by("bucket")
        )
        res = await db.execute(stmt)
        rows = res.all()

        points = [
            MetricDataPoint(
                timestamp=row.bucket,
                value=float(row.error_count),
                service_name=service_name,
            )
            for row in rows
        ]
        if not points:
            # Baseline placeholder points if telemetry is sparse
            points = [
                MetricDataPoint(
                    timestamp=now - timedelta(minutes=i),
                    value=0.0,
                    service_name=service_name,
                )
                for i in range(10, 0, -1)
            ]

        service = AnomalyService(db=db)
        request = AnomalyDetectionRequest(
            service_name=service_name,
            metric_name=metric_name,
            data_points=points,
            method=DetectionMethod(method),
            sensitivity=sensitivity,
        )
        anomalies = await service.detect_and_record_anomalies(request)
        return {
            "service_name": service_name,
            "method": method,
            "evaluated_points": len(points),
            "anomalies_detected": len(anomalies),
            "anomalies": [a.model_dump() for a in anomalies],
        }


# 5. get_incident_details
async def mcp_get_incident_details(
    incident_id: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve incident status, blast radius, severity, and correlated events.
    """
    authenticator.authorize_read_access(auth_token)
    async with async_session_maker() as db:
        service = IncidentService(db=db)
        try:
            detail = await service.get_incident(incident_id)
            return {"incident": detail.model_dump()}
        except EntityNotFoundError:
            return {"error": f"Incident '{incident_id}' not found.", "status": "NOT_FOUND"}


# 6. get_incident_timeline
async def mcp_get_incident_timeline(
    incident_id: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve strictly ordered progression milestones for an incident timeline.
    """
    authenticator.authorize_read_access(auth_token)
    async with async_session_maker() as db:
        service = IncidentService(db=db)
        try:
            timeline = await service.get_timeline(incident_id)
            return {"timeline": timeline.model_dump()}
        except EntityNotFoundError:
            return {"error": f"Incident '{incident_id}' not found.", "status": "NOT_FOUND"}


# 7. find_related_incidents
async def mcp_find_related_incidents(
    service_name: str,
    lookback_days: int = 30,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Find past or co-occurring incidents involving the specified service.
    """
    authenticator.authorize_read_access(auth_token)
    async with async_session_maker() as db:
        service = IncidentService(db=db)
        incidents, total = await service.list_incidents(
            lead_service=service_name,
            limit=20,
        )
        return {
            "service_name": service_name,
            "lookback_days": lookback_days,
            "total_related": total,
            "incidents": [inc.model_dump() for inc in incidents],
        }


# 8. search_historical_incidents
async def mcp_search_historical_incidents(
    query: str,
    limit: int = 5,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Semantic vector search against historical post-mortems and operational runbooks.
    """
    authenticator.authorize_read_access(auth_token)
    async with async_session_maker() as db:
        service = RAGService(db=db)
        request = SemanticSearchRequest(
            query=query,
            limit=min(limit, 10),
            min_similarity=0.4,
        )
        res = await service.search(request)
        return {
            "query": query,
            "matches_found": res.total_results,
            "results": [r.model_dump() for r in res.results],
        }


# 9. get_service_health
async def mcp_get_service_health(
    service_name: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Assess service operational health from active incidents, error rates, and anomalies.
    """
    authenticator.authorize_read_access(auth_token)
    async with async_session_maker() as db:
        now = datetime.now(UTC)
        cutoff_15m = now - timedelta(minutes=15)

        # 1. Check recent error count
        err_stmt = select(func.count(LogEventModel.id)).where(
            LogEventModel.service_name == service_name,
            LogEventModel.timestamp >= cutoff_15m,
            LogEventModel.severity.in_(["ERROR", "CRITICAL"]),
        )
        err_res = await db.execute(err_stmt)
        recent_errors = err_res.scalar() or 0

        # 2. Check active incidents
        inc_stmt = select(func.count(IncidentModel.id)).where(
            IncidentModel.lead_service == service_name,
            IncidentModel.status.in_(["DETECTED", "INVESTIGATING", "IDENTIFIED"]),
        )
        inc_res = await db.execute(inc_stmt)
        active_incidents = inc_res.scalar() or 0

        # Determine health status
        if active_incidents > 0 or recent_errors > 50:
            health_status = "CRITICAL"
        elif recent_errors > 10:
            health_status = "DEGRADED"
        else:
            health_status = "HEALTHY"

        return {
            "service_name": service_name,
            "status": health_status,
            "active_incidents": active_incidents,
            "errors_last_15m": recent_errors,
            "evaluated_at": now.isoformat(),
        }


# 10. generate_incident_report
async def mcp_generate_incident_report(
    incident_id: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Generate an evidence-grounded AI Root Cause Analysis (RCA) report for an incident.
    """
    authenticator.authorize_read_access(auth_token)
    async with async_session_maker() as db:
        service = RCAService(db=db)
        try:
            rca = await service.generate_rca(RCARequest(incident_id=incident_id))
            return {"rca_report": rca.model_dump()}
        except EntityNotFoundError:
            return {"error": f"Incident '{incident_id}' not found.", "status": "NOT_FOUND"}
