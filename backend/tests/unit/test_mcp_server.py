"""Unit tests for the TraceMind Model Context Protocol (MCP) server, tools, and auth."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import EntityNotFoundError
from app.mcp.auth import MCPAuthenticator, MCPAuthError
from app.mcp.server import create_mcp_server
from app.mcp.tools import (
    mcp_analyse_error_pattern,
    mcp_detect_anomalies,
    mcp_find_related_incidents,
    mcp_generate_incident_report,
    mcp_get_incident_details,
    mcp_get_incident_timeline,
    mcp_get_log_details,
    mcp_get_service_health,
    mcp_search_historical_incidents,
    mcp_search_logs,
)
from app.schemas.incident import (
    IncidentDetailResponse,
    IncidentResponse,
    IncidentSeverity,
    IncidentStatus,
    IncidentTimeline,
)
from app.schemas.log_event import CanonicalLogEvent
from app.schemas.rca import LikelihoodLevel, RCAResponse, RootCauseHypothesis


def test_mcp_authenticator() -> None:
    """Verify MCPAuthenticator validates tokens and raises on invalid tokens."""
    auth = MCPAuthenticator(api_key="super-secret-mcp-key")

    assert auth.verify_token("super-secret-mcp-key") is True
    assert auth.verify_token("wrong-key") is False

    with pytest.raises(MCPAuthError, match="Unauthorized"):
        auth.authorize_read_access("invalid-token")


@pytest.mark.asyncio
async def test_mcp_server_initialization() -> None:
    """Verify MCPServer registers all 10 tools."""
    server = create_mcp_server()
    assert server.name == "TraceMind AI"

    # List tools from server
    tool_list = await server.list_tools()
    tool_names = {t.name for t in tool_list}

    expected_tools = {
        "search_logs",
        "get_log_details",
        "analyse_error_pattern",
        "detect_anomalies",
        "get_incident_details",
        "get_incident_timeline",
        "find_related_incidents",
        "search_historical_incidents",
        "get_service_health",
        "generate_incident_report",
    }
    assert expected_tools.issubset(tool_names)


@pytest.mark.asyncio
async def test_mcp_search_logs_tool() -> None:
    """Verify mcp_search_logs tool delegates to LogService."""
    now = datetime.now(UTC)
    mock_event = CanonicalLogEvent(
        event_id="evt-mcp-1",
        timestamp=now,
        severity="ERROR",
        service_name="payment-service",
        message="Card decline error",
    )

    with patch("app.mcp.tools.LogService") as MockService:
        instance = MockService.return_value
        instance.search_logs = AsyncMock(return_value=([mock_event], 1))

        res = await mcp_search_logs(query="card decline", service_name="payment-service")
        assert res["total_matches"] == 1
        assert res["returned_count"] == 1
        assert res["events"][0]["event_id"] == "evt-mcp-1"


@pytest.mark.asyncio
async def test_mcp_get_log_details_tool() -> None:
    """Verify mcp_get_log_details tool returns event or error object."""
    now = datetime.now(UTC)
    mock_event = CanonicalLogEvent(
        event_id="evt-mcp-2",
        timestamp=now,
        severity="INFO",
        service_name="auth-service",
        message="Login successful",
    )

    with patch("app.mcp.tools.LogService") as MockService:
        instance = MockService.return_value
        # 1. Success case
        instance.get_by_event_id = AsyncMock(return_value=mock_event)
        res = await mcp_get_log_details(event_id="evt-mcp-2")
        assert "event" in res
        assert res["event"]["event_id"] == "evt-mcp-2"

        # 2. Not found case
        instance.get_by_event_id = AsyncMock(return_value=None)
        err_res = await mcp_get_log_details(event_id="non-existent")
        assert "error" in err_res
        assert err_res["status"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_mcp_analyse_error_pattern_tool() -> None:
    """Verify mcp_analyse_error_pattern aggregates recurring error signatures."""
    mock_row = MagicMock()
    mock_row.error_signature = "sig-abc-123"
    mock_row.service_name = "payment-service"
    mock_row.exception_type = "DatabaseTimeout"
    mock_row.occurrence_count = 42
    mock_row.first_seen = datetime.now(UTC)
    mock_row.last_seen = datetime.now(UTC)

    with patch("app.mcp.tools.async_session_maker") as mock_session_maker:
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        mock_db_res = MagicMock()
        mock_db_res.all.return_value = [mock_row]
        mock_session.execute.return_value = mock_db_res

        res = await mcp_analyse_error_pattern(service_name="payment-service")
        assert res["service_name"] == "payment-service"
        assert res["total_patterns"] == 1
        assert res["patterns"][0]["error_signature"] == "sig-abc-123"
        assert res["patterns"][0]["occurrence_count"] == 42


@pytest.mark.asyncio
async def test_mcp_detect_anomalies_tool() -> None:
    """Verify mcp_detect_anomalies delegates to AnomalyService."""
    with (
        patch("app.mcp.tools.async_session_maker") as mock_session_maker,
        patch("app.mcp.tools.AnomalyService") as MockAnomalyService,
    ):
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        mock_db_res = MagicMock()
        mock_db_res.all.return_value = []
        mock_session.execute.return_value = mock_db_res

        instance = MockAnomalyService.return_value
        instance.detect_and_record_anomalies = AsyncMock(return_value=[])

        res = await mcp_detect_anomalies(service_name="checkout-service")
        assert res["service_name"] == "checkout-service"
        assert res["anomalies_detected"] == 0


@pytest.mark.asyncio
async def test_mcp_get_incident_details_and_timeline() -> None:
    """Verify get_incident_details and get_incident_timeline tools."""
    now = datetime.now(UTC)
    mock_detail = IncidentDetailResponse(
        id=str(uuid4()),
        incident_id="inc-mcp-100",
        title="High error rate",
        status=IncidentStatus.INVESTIGATING,
        severity=IncidentSeverity.CRITICAL,
        lead_service="auth-service",
        affected_services=["auth-service"],
        error_signatures=[],
        started_at=now,
        detected_at=now,
        created_at=now,
        updated_at=now,
    )
    mock_timeline = IncidentTimeline(
        incident_id="inc-mcp-100",
        started_at=now,
        detected_at=now,
        total_events=1,
    )

    with patch("app.mcp.tools.IncidentService") as MockService:
        instance = MockService.return_value
        instance.get_incident = AsyncMock(return_value=mock_detail)
        instance.get_timeline = AsyncMock(return_value=mock_timeline)

        # 1. Incident details
        res = await mcp_get_incident_details("inc-mcp-100")
        assert res["incident"]["incident_id"] == "inc-mcp-100"

        # 2. Timeline
        t_res = await mcp_get_incident_timeline("inc-mcp-100")
        assert t_res["timeline"]["incident_id"] == "inc-mcp-100"

        # 3. Not found handling
        instance.get_incident = AsyncMock(
            side_effect=EntityNotFoundError(entity="Incident", entity_id="missing")
        )
        instance.get_timeline = AsyncMock(
            side_effect=EntityNotFoundError(entity="Timeline", entity_id="missing")
        )
        assert (await mcp_get_incident_details("missing"))["status"] == "NOT_FOUND"
        assert (await mcp_get_incident_timeline("missing"))["status"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_mcp_find_related_and_search_historical() -> None:
    """Verify find_related_incidents and search_historical_incidents tools."""
    now = datetime.now(UTC)
    mock_inc = IncidentResponse(
        id=str(uuid4()),
        incident_id="inc-rel-1",
        title="Related issue",
        status=IncidentStatus.RESOLVED,
        severity=IncidentSeverity.MEDIUM,
        lead_service="order-service",
        affected_services=["order-service"],
        error_signatures=[],
        started_at=now,
        detected_at=now,
        created_at=now,
        updated_at=now,
    )

    with (
        patch("app.mcp.tools.IncidentService") as MockIncService,
        patch("app.mcp.tools.RAGService") as MockRAGService,
    ):
        mock_inc_inst = MockIncService.return_value
        mock_inc_inst.list_incidents = AsyncMock(return_value=([mock_inc], 1))

        mock_rag_inst = MockRAGService.return_value
        mock_rag_inst.search = AsyncMock(return_value=MagicMock(total_results=0, results=[]))

        # Related incidents
        rel_res = await mcp_find_related_incidents(service_name="order-service")
        assert rel_res["total_related"] == 1
        assert rel_res["incidents"][0]["incident_id"] == "inc-rel-1"

        # Search historical
        hist_res = await mcp_search_historical_incidents(query="database crash")
        assert hist_res["query"] == "database crash"
        assert hist_res["matches_found"] == 0


@pytest.mark.asyncio
async def test_mcp_get_service_health() -> None:
    """Verify mcp_get_service_health calculates status correctly."""
    with patch("app.mcp.tools.async_session_maker") as mock_session_maker:
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        # 1. Healthy (0 errors, 0 active incidents)
        mock_res_0 = MagicMock()
        mock_res_0.scalar.return_value = 0
        mock_session.execute.side_effect = [mock_res_0, mock_res_0]
        h_res = await mcp_get_service_health(service_name="payment-service")
        assert h_res["status"] == "HEALTHY"

        # 2. Degraded (15 errors, 0 active incidents)
        mock_res_15 = MagicMock()
        mock_res_15.scalar.return_value = 15
        mock_session.execute.side_effect = [mock_res_15, mock_res_0]
        d_res = await mcp_get_service_health(service_name="payment-service")
        assert d_res["status"] == "DEGRADED"

        # 3. Critical (1 active incident)
        mock_res_active = MagicMock()
        mock_res_active.scalar.return_value = 1
        mock_session.execute.side_effect = [mock_res_0, mock_res_active]
        c_res = await mcp_get_service_health(service_name="payment-service")
        assert c_res["status"] == "CRITICAL"


@pytest.mark.asyncio
async def test_mcp_generate_incident_report() -> None:
    """Verify mcp_generate_incident_report generates RCA report."""
    now = datetime.now(UTC)
    hyp = RootCauseHypothesis(
        hypothesis_id="hyp-mcp-1",
        title="Database lock",
        description="Deadlock in payment table",
        likelihood=LikelihoodLevel.HIGH,
        confidence_score=0.9,
    )
    mock_rca = RCAResponse(
        incident_id="inc-mcp-report",
        executive_summary="Summary of failure.",
        hypotheses=[hyp],
        primary_root_cause=None,
        affected_components=["payment-service"],
        cascading_propagation=[],
        immediate_mitigation_steps=["Restart pod"],
        preventive_actions=[],
        recommended_runbooks=[],
        diagnostic_commands=[],
        uncertainty_disclaimer="Disclaimer",
        generated_at=now,
        model_used="gpt-4o-mini",
    )

    with patch("app.mcp.tools.RCAService") as MockRCAService:
        instance = MockRCAService.return_value
        instance.generate_rca = AsyncMock(return_value=mock_rca)

        res = await mcp_generate_incident_report("inc-mcp-report")
        assert "rca_report" in res
        assert res["rca_report"]["incident_id"] == "inc-mcp-report"

        # Not found case
        instance.generate_rca = AsyncMock(
            side_effect=EntityNotFoundError(entity="Incident", entity_id="missing")
        )
        err_res = await mcp_generate_incident_report("missing")
        assert err_res["status"] == "NOT_FOUND"
