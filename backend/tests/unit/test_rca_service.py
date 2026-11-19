"""Unit tests for RCAService orchestration."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import EntityNotFoundError
from app.schemas.incident import (
    IncidentDetailResponse,
    IncidentSeverity,
    IncidentStatus,
)
from app.schemas.rag import DocumentSourceType, SearchResultItem, SemanticSearchResponse
from app.schemas.rca import (
    InvestigationChatRequest,
    RCARequest,
)
from app.services.rca_service import RCAService


@pytest.fixture
def mock_incident() -> IncidentDetailResponse:
    now = datetime.now(UTC)
    return IncidentDetailResponse(
        id="uuid-test-01",
        incident_id="inc-rca-orch",
        title="Payment gateway failure",
        status=IncidentStatus.INVESTIGATING,
        severity=IncidentSeverity.CRITICAL,
        lead_service="payment-service",
        affected_services=["payment-service"],
        error_signatures=["sig-db"],
        started_at=now,
        detected_at=now,
        correlated_event_count=0,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_rca_service_generate_rca(mock_incident: IncidentDetailResponse) -> None:
    """Verify RCAService orchestrates incident retrieval, RAG search, and RCA generation."""
    mock_db = AsyncMock()
    service = RCAService(db=mock_db)

    # Mock incident_service.get_incident
    service.incident_service.get_incident = AsyncMock(return_value=mock_incident)  # type: ignore[method-assign]

    # Mock anomaly_service.list_anomalies
    service.anomaly_service.list_anomalies = AsyncMock(return_value=([], 0))  # type: ignore[method-assign]

    # Mock rag_service.search
    search_item = SearchResultItem(
        document_id="doc-1",
        title="Postgres Runbook",
        source_type=DocumentSourceType.RUNBOOK,
        service_name="payment-service",
        section_title="## Pool",
        chunk_index=0,
        content="Increase max_connections",
        similarity_score=0.92,
        citation_reference="[RUNBOOK: Postgres Runbook, §## Pool]",
    )
    service.rag_service.search = AsyncMock(  # type: ignore[method-assign]
        return_value=SemanticSearchResponse(query="q", total_results=1, results=[search_item])
    )

    req = RCARequest(incident_id="inc-rca-orch", include_rag_context=True)
    rca = await service.generate_rca(req)

    assert rca.incident_id == "inc-rca-orch"
    assert len(rca.hypotheses) >= 1
    assert rca.primary_root_cause is not None


@pytest.mark.asyncio
async def test_rca_service_investigate_chat(mock_incident: IncidentDetailResponse) -> None:
    """Verify RCAService orchestrates conversational turn."""
    mock_db = AsyncMock()
    service = RCAService(db=mock_db)

    service.incident_service.get_incident = AsyncMock(return_value=mock_incident)  # type: ignore[method-assign]
    service.rag_service.search = AsyncMock(  # type: ignore[method-assign]
        return_value=SemanticSearchResponse(query="q", total_results=0, results=[])
    )

    req = InvestigationChatRequest(
        incident_id="inc-rca-orch",
        query="What is the lead service?",
    )
    resp = await service.investigate_chat(req)

    assert resp.incident_id == "inc-rca-orch"
    assert len(resp.answer) > 0


@pytest.mark.asyncio
async def test_rca_service_rag_failure_fallback(mock_incident: IncidentDetailResponse) -> None:
    """Verify generate_rca gracefully continues if RAG search encounters an exception."""
    mock_db = AsyncMock()
    service = RCAService(db=mock_db)

    service.incident_service.get_incident = AsyncMock(return_value=mock_incident)  # type: ignore[method-assign]
    service.anomaly_service.list_anomalies = AsyncMock(return_value=([], 0))  # type: ignore[method-assign]
    service.rag_service.search = AsyncMock(side_effect=RuntimeError("Vector index unavailable"))  # type: ignore[method-assign]

    req = RCARequest(incident_id="inc-rca-orch", include_rag_context=True)
    rca = await service.generate_rca(req)
    assert rca.incident_id == "inc-rca-orch"
    assert len(rca.hypotheses) >= 1


@pytest.mark.asyncio
async def test_rca_service_missing_incident_id_raises() -> None:
    """Verify generate_rca and investigate_chat raise EntityNotFoundError if incident_id is missing."""
    mock_db = AsyncMock()
    service = RCAService(db=mock_db)

    with pytest.raises(EntityNotFoundError):
        await service.generate_rca(RCARequest(incident_id=None))

    with pytest.raises(EntityNotFoundError):
        await service.investigate_chat(
            InvestigationChatRequest(incident_id=None, query="test query")
        )
