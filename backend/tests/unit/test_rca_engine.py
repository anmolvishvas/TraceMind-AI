"""Unit tests for RCAEngine."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.llm.client import LLMClient
from app.llm.rca_engine import RCAEngine
from app.schemas.anomaly import AnomalyRecord, AnomalySeverity, AnomalyType, DetectionMethod
from app.schemas.incident import (
    CorrelationType,
    IncidentDetailResponse,
    IncidentEventCorrelation,
    IncidentSeverity,
    IncidentStatus,
    IncidentTimeline,
    MilestoneType,
    TimelineMilestone,
)
from app.schemas.rag import DocumentSourceType, SearchResultItem
from app.schemas.rca import LikelihoodLevel


@pytest.fixture
def sample_incident_detail() -> IncidentDetailResponse:
    now = datetime.now(UTC)
    milestones = [
        TimelineMilestone(
            milestone_type=MilestoneType.FIRST_TRIGGER,
            timestamp=now,
            service_name="payment-service",
            title="Initial timeout",
            description="Initial timeout error detected",
        ),
        TimelineMilestone(
            milestone_type=MilestoneType.ROOT_EXCEPTION,
            timestamp=now,
            service_name="payment-service",
            title="Database failure",
            description="OperationalError: could not connect to server",
        ),
    ]
    timeline = IncidentTimeline(
        incident_id="inc-test-rca",
        started_at=now,
        detected_at=now,
        total_events=2,
        milestones=milestones,
        duration_seconds=120,
    )
    correlations = [
        IncidentEventCorrelation(
            correlation_id="c1",
            incident_id="inc-test-rca",
            event_id="evt-db-timeout",
            correlation_type=CorrelationType.CONFIRMED_CAUSAL,
            confidence_score=1.0,
            reason="Trace ID match",
            timestamp=now,
            service_name="payment-service",
            severity="ERROR",
            message="Database connection timed out",
        )
    ]
    return IncidentDetailResponse(
        id="uuid-test-02",
        incident_id="inc-test-rca",
        title="Payment database timeout",
        status=IncidentStatus.INVESTIGATING,
        severity=IncidentSeverity.CRITICAL,
        lead_service="payment-service",
        affected_services=["payment-service", "checkout-api"],
        error_signatures=["sig-db-conn"],
        started_at=now,
        detected_at=now,
        correlated_event_count=1,
        created_at=now,
        updated_at=now,
        timeline=timeline,
        correlations=correlations,
    )


@pytest.mark.asyncio
async def test_rca_engine_analysis(sample_incident_detail: IncidentDetailResponse) -> None:
    """Verify RCAEngine generates evidence-grounded analysis with mock LLM client."""
    client = LLMClient(mock_mode=True)
    engine = RCAEngine(llm_client=client)

    now = datetime.now(UTC)
    anomalies = [
        AnomalyRecord(
            anomaly_id="anom-01",
            service_name="payment-service",
            timestamp=now,
            metric_name="error_rate",
            current_value=45.0,
            baseline_mean=5.0,
            baseline_std=1.0,
            threshold=8.0,
            anomaly_score=0.98,
            confidence=0.95,
            severity=AnomalySeverity.CRITICAL,
            anomaly_type=AnomalyType.SPIKE,
            detection_method=DetectionMethod.Z_SCORE,
        )
    ]
    runbooks = [
        SearchResultItem(
            document_id="doc-rb-db",
            title="Database Saturation Runbook",
            source_type=DocumentSourceType.RUNBOOK,
            service_name="payment-service",
            section_title="## Triage",
            chunk_index=0,
            content="Check pool sizes in config.",
            similarity_score=0.91,
            citation_reference="[RUNBOOK: Database Saturation, §## Triage]",
        )
    ]

    rca = await engine.analyze_incident(
        incident=sample_incident_detail,
        anomalies=anomalies,
        runbooks=runbooks,
        additional_notes="Reported by tier 1 support",
    )

    assert rca.incident_id == "inc-test-rca"
    assert len(rca.hypotheses) >= 1
    assert rca.primary_root_cause is not None
    assert rca.primary_root_cause.likelihood in (LikelihoodLevel.HIGH, LikelihoodLevel.CONFIRMED)
    assert len(rca.primary_root_cause.supporting_evidence) >= 1
    assert len(rca.diagnostic_commands) >= 1
    assert len(rca.immediate_mitigation_steps) >= 1
    assert "falsification_checks" in rca.primary_root_cause.model_dump()


@pytest.mark.asyncio
async def test_rca_engine_fallback_empty_hypotheses(
    sample_incident_detail: IncidentDetailResponse,
) -> None:
    """Verify RCAEngine handles empty LLM hypothesis output gracefully."""
    mock_client = AsyncMock()
    mock_client.model = "gpt-4o-mini"
    mock_client.generate_json.return_value = {
        "executive_summary": "Inconclusive logs.",
        "hypotheses": [],
    }

    engine = RCAEngine(llm_client=mock_client)
    rca = await engine.analyze_incident(incident=sample_incident_detail)

    assert len(rca.hypotheses) == 1
    assert rca.hypotheses[0].likelihood == LikelihoodLevel.LOW
