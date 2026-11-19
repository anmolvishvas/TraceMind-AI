"""Unit tests for ChaosService and chaos failure simulation endpoints."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db_session, get_redis
from app.main import app
from app.schemas.chaos import ChaosScenario, ChaosSimulateRequest
from app.services.chaos_service import ChaosService


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    # Mock execute for RAG and RCA lookups
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
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


def test_get_available_scenarios(mock_db: AsyncMock) -> None:
    """Test retrieving catalog of preconfigured chaos scenarios."""
    service = ChaosService(db=mock_db)
    scenarios = service.get_available_scenarios()

    assert len(scenarios) == 4
    scenario_ids = [s.scenario for s in scenarios]
    assert ChaosScenario.DB_POOL_STARVATION in scenario_ids
    assert ChaosScenario.REDIS_CACHE_FAILOVER in scenario_ids
    assert ChaosScenario.KAFKA_CONSUMER_LAG in scenario_ids
    assert ChaosScenario.POD_MEMORY_LEAK in scenario_ids

    for sc in scenarios:
        assert sc.name
        assert sc.description
        assert sc.lead_service
        assert len(sc.affected_services) > 0
        assert sc.severity in ("HIGH", "CRITICAL")
        assert len(sc.symptoms) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_service", "expected_severity"),
    [
        (ChaosScenario.DB_POOL_STARVATION, "payment-gateway", "CRITICAL"),
        (ChaosScenario.REDIS_CACHE_FAILOVER, "auth-service", "HIGH"),
        (ChaosScenario.KAFKA_CONSUMER_LAG, "order-processing-worker", "HIGH"),
        (ChaosScenario.POD_MEMORY_LEAK, "search-indexer", "CRITICAL"),
    ],
)
async def test_simulate_incident_scenarios(
    mock_db: AsyncMock,
    scenario: ChaosScenario,
    expected_service: str,
    expected_severity: str,
) -> None:
    """Test full telemetry injection across each failure scenario."""
    service = ChaosService(db=mock_db)
    req = ChaosSimulateRequest(scenario=scenario, custom_title=f"Custom {scenario.value}")
    resp = await service.simulate_incident(req)

    assert resp.scenario == scenario
    assert resp.incident.lead_service == expected_service
    assert resp.incident.severity == expected_severity
    assert resp.incident.title == f"Custom {scenario.value}"
    assert resp.injected_logs_count > 0
    assert resp.injected_anomalies_count > 0
    assert resp.runbook_title
    assert mock_db.commit.called


def test_api_list_chaos_scenarios(client: TestClient) -> None:
    """Test GET /api/v1/incidents/scenarios endpoint."""
    response = client.get("/api/v1/incidents/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 4
    assert any(s["scenario"] == "db_pool_starvation" for s in data)


def test_api_simulate_chaos_incident_default(client: TestClient) -> None:
    """Test POST /api/v1/incidents/simulate endpoint with default payload."""
    response = client.post("/api/v1/incidents/simulate", json={})
    assert response.status_code == 201
    data = response.json()
    assert "incident" in data
    assert data["scenario"] == "db_pool_starvation"
    assert data["incident"]["lead_service"] == "payment-gateway"
    assert data["injected_logs_count"] > 0


def test_api_simulate_chaos_incident_custom(client: TestClient) -> None:
    """Test POST /api/v1/incidents/simulate endpoint with specific scenario."""
    response = client.post(
        "/api/v1/incidents/simulate",
        json={
            "scenario": "redis_cache_failover",
            "custom_title": "Simulated Redis Outage",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["scenario"] == "redis_cache_failover"
    assert data["incident"]["lead_service"] == "auth-service"
    assert data["incident"]["title"] == "Simulated Redis Outage"
