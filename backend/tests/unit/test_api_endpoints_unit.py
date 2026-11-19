"""Unit tests for FastAPI REST API endpoints using dependency overrides."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db_session, get_redis
from app.main import app
from app.models.anomaly import AnomalyModel
from app.models.incident import IncidentCorrelationModel, IncidentModel
from app.models.rag import DocumentChunkModel, KnowledgeDocumentModel
from app.schemas.incident import IncidentSeverity, IncidentStatus


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def client(mock_db: AsyncMock, mock_redis: AsyncMock) -> TestClient:
    """Provide TestClient with mocked dependencies."""

    async def override_get_db() -> Any:
        yield mock_db

    async def override_get_redis() -> Any:
        return mock_redis

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_health_endpoint(client: TestClient) -> None:
    """Test health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_anomalies_detect_endpoint(client: TestClient, mock_db: AsyncMock) -> None:
    """Test POST /api/v1/anomalies/detect."""
    now_iso = datetime.now(UTC).isoformat()
    payload = {
        "service_name": "checkout-service",
        "metric_name": "error_rate",
        "method": "Z_SCORE",
        "sensitivity": 1.0,
        "data_points": [
            {"timestamp": now_iso, "value": 10.0, "service_name": "checkout-service"}
            for _ in range(20)
        ]
        + [{"timestamp": now_iso, "value": 150.0, "service_name": "checkout-service"}],
    }
    response = client.post("/api/v1/anomalies/detect", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["service_name"] == "checkout-service"


def test_anomalies_list_endpoint(client: TestClient, mock_db: AsyncMock) -> None:
    """Test GET /api/v1/anomalies."""
    mock_anomaly = AnomalyModel(
        id=str(uuid4()),
        anomaly_id="anom-api-1",
        service_name="payment-service",
        timestamp=datetime.now(UTC),
        metric_name="latency_p99",
        current_value=450.0,
        baseline_mean=50.0,
        baseline_std=10.0,
        threshold=80.0,
        anomaly_score=0.99,
        severity="CRITICAL",
        detection_method="Z_SCORE",
        details={},
        created_at=datetime.now(UTC),
    )
    mock_count = MagicMock()
    mock_count.scalar.return_value = 1
    mock_rows = MagicMock()
    mock_rows.scalars.return_value.all.return_value = [mock_anomaly]

    mock_db.execute.side_effect = [mock_count, mock_rows]

    response = client.get("/api/v1/anomalies?service_name=payment-service&severity=CRITICAL")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["anomaly_id"] == "anom-api-1"


def test_incidents_correlate_endpoint(client: TestClient, mock_db: AsyncMock) -> None:
    """Test POST /api/v1/incidents/correlate."""
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_res

    response = client.post("/api/v1/incidents/correlate?lookback_minutes=15")
    assert response.status_code == 201
    assert response.json() == []


def test_incidents_list_endpoint(client: TestClient, mock_db: AsyncMock) -> None:
    """Test GET /api/v1/incidents."""
    mock_inc = IncidentModel(
        id=str(uuid4()),
        incident_id="inc-api-100",
        title="Payment gateway failure",
        status=IncidentStatus.DETECTED.value,
        severity=IncidentSeverity.CRITICAL.value,
        lead_service="payment-service",
        affected_services=["payment-service"],
        error_signatures=[],
        started_at=datetime.now(UTC),
        detected_at=datetime.now(UTC),
        metadata_={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_inc.correlations = []

    mock_count = MagicMock()
    mock_count.scalar.return_value = 1
    mock_rows = MagicMock()
    mock_rows.scalars.return_value.all.return_value = [mock_inc]

    mock_db.execute.side_effect = [mock_count, mock_rows]

    response = client.get("/api/v1/incidents?status=DETECTED&severity=CRITICAL")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["incident_id"] == "inc-api-100"


def test_incident_detail_and_timeline_endpoint(client: TestClient, mock_db: AsyncMock) -> None:
    """Test GET /api/v1/incidents/{incident_id} and timeline."""
    now = datetime.now(UTC)
    mock_inc = IncidentModel(
        id=str(uuid4()),
        incident_id="inc-api-200",
        title="High error rate",
        status=IncidentStatus.INVESTIGATING.value,
        severity=IncidentSeverity.HIGH.value,
        lead_service="auth-service",
        affected_services=["auth-service"],
        error_signatures=[],
        started_at=now,
        detected_at=now,
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    mock_corr = IncidentCorrelationModel(
        id=str(uuid4()),
        incident_id=mock_inc.id,
        event_id="evt-99",
        correlation_type="CONFIRMED_CAUSAL",
        confidence_score=1.0,
        reason="Trace ID match",
        created_at=now,
    )
    mock_inc.correlations = [mock_corr]

    mock_inc_res = MagicMock()
    mock_inc_res.scalar_one_or_none.return_value = mock_inc

    mock_evts_res = MagicMock()
    mock_evts_res.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [mock_inc_res, mock_evts_res]

    response = client.get("/api/v1/incidents/inc-api-200")
    assert response.status_code == 200
    assert response.json()["incident_id"] == "inc-api-200"

    # Timeline endpoint
    mock_db.execute.side_effect = [mock_inc_res, mock_evts_res]
    t_response = client.get("/api/v1/incidents/inc-api-200/timeline")
    assert t_response.status_code == 200
    assert t_response.json()["incident_id"] == "inc-api-200"


def test_incident_status_update_endpoint(client: TestClient, mock_db: AsyncMock) -> None:
    """Test PATCH /api/v1/incidents/{incident_id}/status."""
    now = datetime.now(UTC)
    mock_inc = IncidentModel(
        id=str(uuid4()),
        incident_id="inc-api-300",
        title="Database lock",
        status=IncidentStatus.INVESTIGATING.value,
        severity=IncidentSeverity.HIGH.value,
        lead_service="db-service",
        affected_services=["db-service"],
        error_signatures=[],
        started_at=now,
        detected_at=now,
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    mock_inc.correlations = []

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_inc
    mock_db.execute.return_value = mock_res

    payload = {
        "new_status": "IDENTIFIED",
        "user_id": "engineer@tracemind.ai",
        "notes": "Identified deadlock in transaction table",
    }
    response = client.patch("/api/v1/incidents/inc-api-300/status", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "IDENTIFIED"


def test_rag_documents_endpoints(client: TestClient, mock_db: AsyncMock) -> None:
    """Test POST, GET, DELETE /api/v1/rag/documents."""
    now = datetime.now(UTC)

    # 1. Create document
    create_payload = {
        "title": "PostgreSQL Recovery Playbook",
        "source_type": "RUNBOOK",
        "service_name": "db-service",
        "category": "database",
        "content": "# Recovery Steps\n1. Check status.\n2. Restart replica.\n\n# Verification\nRun select 1.",
        "metadata": {"author": "sre"},
    }
    create_resp = client.post("/api/v1/rag/documents", json=create_payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["title"] == "PostgreSQL Recovery Playbook"
    assert created_data["total_chunks"] >= 2

    # 2. List documents
    mock_doc = KnowledgeDocumentModel(
        id=str(uuid4()),
        document_id="doc-list-1",
        title="Redis Runbook",
        source_type="RUNBOOK",
        service_name="cache-service",
        category="cache",
        content="Cache runbook",
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    mock_count = MagicMock()
    mock_count.scalar.return_value = 1
    mock_rows = MagicMock()
    mock_rows.scalars.return_value.all.return_value = [mock_doc]

    mock_db.execute.side_effect = [mock_count, mock_rows]
    list_resp = client.get("/api/v1/rag/documents?service_name=cache-service")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 3. Get document detail
    mock_chunk = DocumentChunkModel(
        id=str(uuid4()),
        document_id=mock_doc.id,
        chunk_index=0,
        content="Step 1",
        section_title="## Triage",
        token_count=5,
        embedding=[0.0] * 1536,
        metadata_={},
        created_at=now,
    )
    mock_doc.chunks = [mock_chunk]

    mock_detail_res = MagicMock()
    mock_detail_res.scalar_one_or_none.return_value = mock_doc
    mock_db.execute.side_effect = [mock_detail_res]

    detail_resp = client.get("/api/v1/rag/documents/doc-list-1")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["document_id"] == "doc-list-1"
    assert len(detail_resp.json()["chunks"]) == 1

    # 4. Delete document
    mock_db.execute.side_effect = [mock_detail_res]
    del_resp = client.delete("/api/v1/rag/documents/doc-list-1")
    assert del_resp.status_code == 204


def test_rag_search_endpoint(client: TestClient, mock_db: AsyncMock) -> None:
    """Test POST /api/v1/rag/search."""
    now = datetime.now(UTC)
    mock_doc = KnowledgeDocumentModel(
        id=str(uuid4()),
        document_id="doc-search-1",
        title="Disk Space Runbook",
        source_type="RUNBOOK",
        service_name="node-service",
        category="infrastructure",
        content="Clear /tmp directory.",
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    mock_chunk = DocumentChunkModel(
        id=str(uuid4()),
        document_id=mock_doc.id,
        chunk_index=0,
        content="Run rm -rf /tmp/stale_*",
        section_title="## Remediation",
        token_count=10,
        embedding=[0.0] * 1536,
        metadata_={},
        created_at=now,
    )

    mock_res = MagicMock()
    # distance = 0.1 -> similarity = 0.9
    mock_res.all.return_value = [(mock_chunk, mock_doc, 0.1)]
    mock_db.execute.return_value = mock_res

    payload = {
        "query": "disk space full on node",
        "service_name": "node-service",
        "limit": 5,
        "min_similarity": 0.5,
    }
    search_resp = client.post("/api/v1/rag/search", json=payload)
    assert search_resp.status_code == 200
    body = search_resp.json()
    assert body["total_results"] == 1
    assert body["results"][0]["document_id"] == "doc-search-1"


def test_incident_rca_and_chat_endpoints(client: TestClient, mock_db: AsyncMock) -> None:
    """Test POST /api/v1/incidents/{incident_id}/rca and /chat."""
    now = datetime.now(UTC)
    mock_inc = IncidentModel(
        id=str(uuid4()),
        incident_id="inc-api-rca",
        title="Payment timeouts",
        status=IncidentStatus.INVESTIGATING.value,
        severity=IncidentSeverity.CRITICAL.value,
        lead_service="payment-service",
        affected_services=["payment-service"],
        error_signatures=["sig-1"],
        started_at=now,
        detected_at=now,
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    mock_corr = IncidentCorrelationModel(
        id=str(uuid4()),
        incident_id=mock_inc.id,
        event_id="evt-rca-1",
        correlation_type="CONFIRMED_CAUSAL",
        confidence_score=1.0,
        reason="Trace match",
        created_at=now,
    )
    mock_inc.correlations = [mock_corr]

    # Query responses for incident fetch
    mock_inc_res = MagicMock()
    mock_inc_res.scalar_one_or_none.return_value = mock_inc

    mock_evts_res = MagicMock()
    mock_evts_res.scalars.return_value.all.return_value = []

    # Count for anomaly fetch
    mock_anom_count = MagicMock()
    mock_anom_count.scalar.return_value = 0
    mock_anom_rows = MagicMock()
    mock_anom_rows.scalars.return_value.all.return_value = []

    # Search result for RAG fetch
    mock_rag_res = MagicMock()
    mock_rag_res.all.return_value = []

    # Sequence of DB executions for RCA endpoint:
    # 1. get_incident (incident query)
    # 2. get_incident (events query)
    # 3. list_anomalies (count query)
    # 4. list_anomalies (rows query)
    # 5. rag search (search query)
    mock_db.execute.side_effect = [
        mock_inc_res,
        mock_evts_res,
        mock_anom_count,
        mock_anom_rows,
        mock_rag_res,
    ]

    rca_resp = client.post("/api/v1/incidents/inc-api-rca/rca", json={"include_rag_context": True})
    assert rca_resp.status_code == 200
    rca_body = rca_resp.json()
    assert rca_body["incident_id"] == "inc-api-rca"
    assert len(rca_body["hypotheses"]) >= 1

    # Sequence of DB executions for Chat endpoint:
    # 1. get_incident (incident query)
    # 2. get_incident (events query)
    # 3. rag search (search query)
    mock_db.execute.side_effect = [
        mock_inc_res,
        mock_evts_res,
        mock_rag_res,
    ]

    chat_payload = {
        "incident_id": "inc-api-rca",
        "query": "What services are affected?",
        "history": [],
    }
    chat_resp = client.post("/api/v1/incidents/inc-api-rca/chat", json=chat_payload)
    assert chat_resp.status_code == 200
    chat_body = chat_resp.json()
    assert chat_body["incident_id"] == "inc-api-rca"
    assert len(chat_body["answer"]) > 0
