"""Unit tests for InvestigationAssistant."""

from datetime import UTC, datetime

import pytest

from app.llm.assistant import InvestigationAssistant
from app.llm.client import LLMClient
from app.schemas.incident import (
    CorrelationType,
    IncidentDetailResponse,
    IncidentEventCorrelation,
    IncidentSeverity,
    IncidentStatus,
)
from app.schemas.rag import DocumentSourceType, SearchResultItem
from app.schemas.rca import InvestigationChatMessage, InvestigationChatRequest


@pytest.fixture
def sample_incident_for_chat() -> IncidentDetailResponse:
    now = datetime.now(UTC)
    correlations = [
        IncidentEventCorrelation(
            correlation_id="c1",
            incident_id="inc-chat-01",
            event_id="evt-100",
            correlation_type=CorrelationType.CONFIRMED_CAUSAL,
            confidence_score=1.0,
            reason="Upstream timeout",
            timestamp=now,
            service_name="payment-service",
            severity="ERROR",
            message="Upstream timeout",
        )
    ]
    return IncidentDetailResponse(
        id="uuid-test-03",
        incident_id="inc-chat-01",
        title="Payment gateway timeout",
        status=IncidentStatus.INVESTIGATING,
        severity=IncidentSeverity.HIGH,
        lead_service="payment-service",
        affected_services=["payment-service"],
        error_signatures=["sig-1"],
        started_at=now,
        detected_at=now,
        correlated_event_count=1,
        created_at=now,
        updated_at=now,
        correlations=correlations,
    )


@pytest.mark.asyncio
async def test_assistant_answer_query(
    sample_incident_for_chat: IncidentDetailResponse,
) -> None:
    """Verify InvestigationAssistant generates grounded answers with citations."""
    client = LLMClient(mock_mode=True)
    assistant = InvestigationAssistant(llm_client=client)

    runbooks = [
        SearchResultItem(
            document_id="doc-rb-01",
            title="Payment Runbook",
            source_type=DocumentSourceType.RUNBOOK,
            service_name="payment-service",
            section_title="## Triage",
            chunk_index=0,
            content="Check database connection pool limit.",
            similarity_score=0.9,
            citation_reference="[RUNBOOK: Payment Runbook, §## Triage]",
        )
    ]

    history = [
        InvestigationChatMessage(
            role="user",
            content="When did this error start?",
            timestamp=datetime.now(UTC),
        ),
        InvestigationChatMessage(
            role="assistant",
            content="It started at 10:00:00 UTC.",
            timestamp=datetime.now(UTC),
        ),
    ]

    req = InvestigationChatRequest(
        incident_id="inc-chat-01",
        query="What was the initial error message?",
        history=history,
    )

    resp = await assistant.answer_query(
        request=req,
        incident=sample_incident_for_chat,
        runbooks=runbooks,
    )

    assert resp.incident_id == "inc-chat-01"
    assert len(resp.answer) > 0
    assert len(resp.citations) >= 1
    assert len(resp.suggested_followups) >= 1
