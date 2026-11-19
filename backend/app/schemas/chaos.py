"""Pydantic schemas for chaos engineering simulation and interactive outage injection."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.incident import IncidentResponse


class ChaosScenario(StrEnum):
    """Supported interactive failure simulation scenarios."""

    DB_POOL_STARVATION = "db_pool_starvation"
    REDIS_CACHE_FAILOVER = "redis_cache_failover"
    KAFKA_CONSUMER_LAG = "kafka_consumer_lag"
    POD_MEMORY_LEAK = "pod_memory_leak"


class ScenarioMetadata(BaseModel):
    """Descriptor and educational metadata for a simulated chaos scenario."""

    scenario: ChaosScenario
    name: str
    description: str
    lead_service: str
    affected_services: list[str]
    severity: str
    symptoms: list[str]
    icon: str = Field(default="zap")


class ChaosSimulateRequest(BaseModel):
    """Payload to trigger an interactive chaos simulation."""

    scenario: ChaosScenario = Field(
        default=ChaosScenario.DB_POOL_STARVATION,
        description="Failure scenario identifier",
    )
    custom_title: str | None = Field(
        default=None,
        description="Optional custom title for the simulated incident",
    )


class ChaosSimulateResponse(BaseModel):
    """Response payload returned following successful chaos injection."""

    incident: IncidentResponse
    scenario: ChaosScenario
    injected_logs_count: int
    injected_anomalies_count: int
    runbook_title: str
    message: str
    extra_details: dict[str, Any] = Field(default_factory=dict)
