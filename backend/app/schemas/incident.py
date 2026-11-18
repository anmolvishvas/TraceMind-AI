"""Pydantic schemas for incident correlation, lifecycle management, and timelines."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class IncidentStatus(StrEnum):
    """Incident lifecycle states strictly enforced by the state machine."""

    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    IDENTIFIED = "IDENTIFIED"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"


class IncidentSeverity(StrEnum):
    """Incident severity classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CorrelationType(StrEnum):
    """Classification of linkage between log events, anomalies, and incidents."""

    CONFIRMED_CAUSAL = "CONFIRMED_CAUSAL"  # Exact trace_id or request_id propagation
    TEMPORAL_SERVICE = "TEMPORAL_SERVICE"  # Sliding temporal window + service dependency
    SIGNATURE_BURST = "SIGNATURE_BURST"  # Spikes of matching error_signature
    CASCADING_FAILURE = "CASCADING_FAILURE"  # Topology-based upstream -> downstream breakdown
    HEURISTIC = "HEURISTIC"  # Keyword/semantic similarity correlation


class MilestoneType(StrEnum):
    """Key progression milestones within an incident timeline."""

    FIRST_TRIGGER = "FIRST_TRIGGER"
    ROOT_EXCEPTION = "ROOT_EXCEPTION"
    CASCADE_PROPAGATION = "CASCADE_PROPAGATION"
    PEAK_IMPACT = "PEAK_IMPACT"
    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    ROOT_CAUSE_IDENTIFIED = "ROOT_CAUSE_IDENTIFIED"
    MITIGATION_APPLIED = "MITIGATION_APPLIED"
    RECOVERY = "RECOVERY"
    RESOLVED = "RESOLVED"


class IncidentEventCorrelation(BaseModel):
    """Mapping between an incident and a supporting log event or anomaly."""

    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    incident_id: str
    event_id: str
    correlation_type: CorrelationType
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    reason: str | None = None
    timestamp: datetime
    service_name: str
    severity: str
    message: str
    error_signature: str | None = None
    trace_id: str | None = None


class TimelineMilestone(BaseModel):
    """Chronological event marker in an incident progression timeline."""

    milestone_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime
    milestone_type: MilestoneType
    service_name: str
    title: str
    description: str
    evidence_event_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentTimeline(BaseModel):
    """Ordered chronological representation of an incident from inception to resolution."""

    incident_id: str
    started_at: datetime
    detected_at: datetime
    resolved_at: datetime | None = None
    duration_seconds: float | None = None
    milestones: list[TimelineMilestone] = Field(default_factory=list)
    total_events: int = 0
    services_involved: list[str] = Field(default_factory=list)


class IncidentCreate(BaseModel):
    """Payload to create a correlated incident."""

    title: str = Field(..., max_length=255)
    description: str | None = None
    lead_service: str = Field(..., max_length=128)
    severity: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM)
    affected_services: list[str] = Field(default_factory=list)
    error_signatures: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentStatusUpdate(BaseModel):
    """Request payload to transition incident lifecycle state."""

    new_status: IncidentStatus = Field(..., description="Target lifecycle status")
    notes: str | None = Field(None, description="Operational investigation or resolution notes")
    user_id: str = Field(..., description="Operator or engineer triggering the transition")
    root_cause_summary: str | None = Field(
        None, description="Required when transitioning to IDENTIFIED or RESOLVED"
    )
    remediation_action: str | None = Field(
        None, description="Action taken when transitioning to MITIGATED or RESOLVED"
    )


class IncidentResponse(BaseModel):
    """Summary response for an incident."""

    id: str
    incident_id: str
    title: str
    description: str | None = None
    status: IncidentStatus
    severity: IncidentSeverity
    lead_service: str
    affected_services: list[str]
    error_signatures: list[str]
    started_at: datetime
    detected_at: datetime
    mitigated_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_notes: str | None = None
    correlated_event_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class IncidentDetailResponse(IncidentResponse):
    """Detailed response containing correlated events and timeline."""

    correlations: list[IncidentEventCorrelation] = Field(default_factory=list)
    timeline: IncidentTimeline | None = None
