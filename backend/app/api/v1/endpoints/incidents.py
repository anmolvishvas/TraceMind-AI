"""REST API endpoints for incident correlation, lifecycle governance, and timelines."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.incident import (
    IncidentDetailResponse,
    IncidentResponse,
    IncidentStatusUpdate,
    IncidentTimeline,
)
from app.schemas.rca import (
    InvestigationChatRequest,
    InvestigationChatResponse,
    RCARequest,
    RCAResponse,
)
from app.services.incident_service import IncidentService
from app.services.rca_service import RCAService

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.post("/correlate", response_model=list[IncidentResponse], status_code=201)
async def correlate_incidents(
    lookback_minutes: int = Query(
        30, ge=1, le=1440, description="Window to search unassigned errors"
    ),
    db: AsyncSession = Depends(get_db_session),
) -> list[IncidentResponse]:
    """
    Execute multi-dimensional incident correlation engine over unassigned errors.
    Clusters events using trace IDs, temporal proximity, service topology, and error signatures.
    """
    service = IncidentService(db=db)
    return await service.correlate_unassigned_events(lookback_minutes=lookback_minutes)


@router.get("", response_model=dict[str, Any], status_code=200)
async def list_incidents(
    status: str | None = Query(
        None,
        description="Filter by status (DETECTED, INVESTIGATING, IDENTIFIED, MITIGATED, RESOLVED)",
    ),
    severity: str | None = Query(
        None, description="Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)"
    ),
    lead_service: str | None = Query(None, description="Filter by lead service"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Query operational incidents with multi-criteria filtering and pagination."""
    service = IncidentService(db=db)
    items, total = await service.list_incidents(
        status=status,
        severity=severity,
        lead_service=lead_service,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [item.model_dump() for item in items],
    }


@router.get("/{incident_id}", response_model=IncidentDetailResponse, status_code=200)
async def get_incident_detail(
    incident_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> IncidentDetailResponse:
    """Retrieve full incident details, correlated events, and computed timeline."""
    service = IncidentService(db=db)
    return await service.get_incident(incident_id)


@router.get("/{incident_id}/timeline", response_model=IncidentTimeline, status_code=200)
async def get_incident_timeline(
    incident_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> IncidentTimeline:
    """Retrieve strictly ordered chronological progression timeline for an incident."""
    service = IncidentService(db=db)
    return await service.get_timeline(incident_id)


@router.patch("/{incident_id}/status", response_model=IncidentResponse, status_code=200)
async def update_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> IncidentResponse:
    """
    Transition incident lifecycle status with state machine governance.
    Requires human attribution and notes to transition to RESOLVED.
    """
    service = IncidentService(db=db)
    return await service.update_status(incident_id, payload)


@router.post("/{incident_id}/rca", response_model=RCAResponse, status_code=200)
async def generate_root_cause_analysis(
    incident_id: str,
    payload: RCARequest | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> RCAResponse:
    """
    Generate an evidence-grounded AI Root Cause Analysis (RCA) for an incident.
    Synthesizes timeline, correlated logs, anomalies, and retrieved historical runbooks.
    """
    service = RCAService(db=db)
    req = payload or RCARequest(incident_id=incident_id)
    # Ensure incident_id matches path
    req.incident_id = incident_id
    return await service.generate_rca(req)


@router.post("/{incident_id}/chat", response_model=InvestigationChatResponse, status_code=200)
async def investigate_chat(
    incident_id: str,
    payload: InvestigationChatRequest,
    db: AsyncSession = Depends(get_db_session),
) -> InvestigationChatResponse:
    """
    Interactive dialogue with the AI incident investigation assistant.
    Grounded in incident live context and operational knowledge.
    """
    service = RCAService(db=db)
    payload.incident_id = incident_id
    return await service.investigate_chat(payload)
