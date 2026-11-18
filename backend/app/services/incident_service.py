"""Service layer managing incident correlation, persistence, lifecycle, and timelines."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from sqlalchemy import desc, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundError
from app.incidents.correlator import IncidentCorrelator
from app.incidents.state_machine import IncidentLifecycleManager
from app.incidents.timeline import IncidentTimelineGenerator
from app.models.incident import IncidentCorrelationModel, IncidentModel
from app.models.log_event import LogEventModel
from app.schemas.incident import (
    CorrelationType,
    IncidentCreate,
    IncidentDetailResponse,
    IncidentEventCorrelation,
    IncidentResponse,
    IncidentSeverity,
    IncidentStatus,
    IncidentStatusUpdate,
    IncidentTimeline,
)
from app.schemas.log_event import CanonicalLogEvent, LogLevel

logger = logging.getLogger("tracemind.services.incident")


class IncidentService:
    """
    Coordinates incident correlation, database transactions, lifecycle transitions,
    and structured timeline generation.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.correlator = IncidentCorrelator()
        self.lifecycle_manager = IncidentLifecycleManager()

    async def correlate_unassigned_events(
        self,
        lookback_minutes: int = 30,
    ) -> list[IncidentResponse]:
        """
        Query unassigned errors within the lookback window, execute multi-dimensional
        correlation, and persist resulting incident clusters.
        """
        cutoff = datetime.now(UTC) - timedelta(minutes=lookback_minutes)

        # 1. Select unassigned error log events
        query = (
            select(LogEventModel)
            .where(
                LogEventModel.timestamp >= cutoff,
                LogEventModel.severity.in_(["ERROR", "CRITICAL"]),
            )
            .order_by(LogEventModel.timestamp.asc())
        )
        res = await self.db.execute(query)
        db_events = res.scalars().all()

        if not db_events:
            return []

        # Convert ORM to CanonicalLogEvent schemas
        canonical_events = [
            CanonicalLogEvent(
                event_id=e.event_id,
                timestamp=e.timestamp,
                severity=cast(LogLevel, e.severity),
                service_name=e.service_name,
                environment=e.environment,
                message=e.message,
                exception_type=e.exception_type,
                stack_trace=e.stack_trace,
                error_signature=e.error_signature,
                request_id=e.request_id,
                trace_id=e.trace_id,
                span_id=e.span_id,
                correlation_id=e.correlation_id,
                source_file=e.source_file,
                line_number=e.line_number,
                metadata=e.attributes,
            )
            for e in db_events
        ]

        # 2. Correlate events into incident clusters
        clusters = self.correlator.correlate_events(canonical_events)

        # 3. Persist each new incident cluster
        created_incidents: list[IncidentResponse] = []
        for incident_create, correlations in clusters:
            resp = await self.create_incident(incident_create, correlations)
            created_incidents.append(resp)

        return created_incidents

    async def create_incident(
        self,
        data: IncidentCreate,
        correlations: list[IncidentEventCorrelation] | None = None,
    ) -> IncidentResponse:
        """Persist a new incident and its event correlation linkages."""
        inc_uuid = str(uuid4())
        inc_id = f"inc-{uuid4().hex[:10]}"
        now = datetime.now(UTC)

        incident_orm = IncidentModel(
            id=inc_uuid,
            incident_id=inc_id,
            title=data.title,
            description=data.description,
            status=IncidentStatus.DETECTED.value,
            severity=data.severity.value,
            lead_service=data.lead_service,
            affected_services=data.affected_services,
            error_signatures=data.error_signatures,
            started_at=data.started_at,
            detected_at=data.detected_at,
            metadata_=data.metadata,
            created_at=now,
            updated_at=now,
        )
        self.db.add(incident_orm)
        await self.db.flush()

        if correlations:
            correlation_records = [
                {
                    "id": str(uuid4()),
                    "incident_id": inc_uuid,
                    "event_id": c.event_id,
                    "correlation_type": c.correlation_type.value,
                    "confidence_score": c.confidence_score,
                    "reason": c.reason,
                    "created_at": now,
                }
                for c in correlations
            ]
            stmt = insert(IncidentCorrelationModel).values(correlation_records)
            await self.db.execute(stmt)

        await self.db.commit()

        return IncidentResponse(
            id=inc_uuid,
            incident_id=inc_id,
            title=data.title,
            description=data.description,
            status=IncidentStatus.DETECTED,
            severity=data.severity,
            lead_service=data.lead_service,
            affected_services=data.affected_services,
            error_signatures=data.error_signatures,
            started_at=data.started_at,
            detected_at=data.detected_at,
            mitigated_at=None,
            resolved_at=None,
            resolved_by=None,
            resolution_notes=None,
            correlated_event_count=len(correlations) if correlations else 0,
            metadata=data.metadata,
            created_at=now,
            updated_at=now,
        )

    async def list_incidents(
        self,
        status: str | None = None,
        severity: str | None = None,
        lead_service: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[IncidentResponse], int]:
        """List incidents with filtering and pagination."""
        base_query = select(IncidentModel)
        count_query = select(func.count()).select_from(IncidentModel)

        filters = []
        if status:
            filters.append(IncidentModel.status == status)
        if severity:
            filters.append(IncidentModel.severity == severity)
        if lead_service:
            filters.append(IncidentModel.lead_service == lead_service)

        if filters:
            base_query = base_query.where(*filters)
            count_query = count_query.where(*filters)

        total_res = await self.db.execute(count_query)
        total = total_res.scalar() or 0

        paginated_query = (
            base_query.options(selectinload(IncidentModel.correlations))
            .order_by(desc(IncidentModel.started_at))
            .limit(limit)
            .offset(offset)
        )
        res = await self.db.execute(paginated_query)
        rows = res.scalars().all()

        items = [
            IncidentResponse(
                id=r.id,
                incident_id=r.incident_id,
                title=r.title,
                description=r.description,
                status=IncidentStatus(r.status),
                severity=IncidentSeverity(r.severity),
                lead_service=r.lead_service,
                affected_services=r.affected_services,
                error_signatures=r.error_signatures,
                started_at=r.started_at,
                detected_at=r.detected_at,
                mitigated_at=r.mitigated_at,
                resolved_at=r.resolved_at,
                resolved_by=r.resolved_by,
                resolution_notes=r.resolution_notes,
                correlated_event_count=len(r.correlations),
                metadata=r.metadata_ or {},
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]
        return items, total

    async def get_incident(self, incident_id: str) -> IncidentDetailResponse:
        """Retrieve full details of an incident by UUID or human-readable incident_id."""
        query = (
            select(IncidentModel)
            .where((IncidentModel.id == incident_id) | (IncidentModel.incident_id == incident_id))
            .options(selectinload(IncidentModel.correlations))
        )
        res = await self.db.execute(query)
        incident = res.scalar_one_or_none()

        if incident is None:
            raise EntityNotFoundError(entity="Incident", entity_id=incident_id)

        # Retrieve correlated event records
        event_ids = [c.event_id for c in incident.correlations]
        correlated_events: list[CanonicalLogEvent] = []
        if event_ids:
            evts_query = select(LogEventModel).where(LogEventModel.event_id.in_(event_ids))
            evts_res = await self.db.execute(evts_query)
            db_evts = evts_res.scalars().all()
            correlated_events = [
                CanonicalLogEvent(
                    event_id=e.event_id,
                    timestamp=e.timestamp,
                    severity=cast(LogLevel, e.severity),
                    service_name=e.service_name,
                    environment=e.environment,
                    message=e.message,
                    exception_type=e.exception_type,
                    stack_trace=e.stack_trace,
                    error_signature=e.error_signature,
                    request_id=e.request_id,
                    trace_id=e.trace_id,
                    span_id=e.span_id,
                    correlation_id=e.correlation_id,
                    source_file=e.source_file,
                    line_number=e.line_number,
                    metadata=e.attributes,
                )
                for e in db_evts
            ]

        # Generate timeline
        timeline = IncidentTimelineGenerator.generate_timeline(
            incident_id=incident.incident_id,
            started_at=incident.started_at,
            detected_at=incident.detected_at,
            resolved_at=incident.resolved_at,
            events=correlated_events,
        )

        correlations = [
            IncidentEventCorrelation(
                correlation_id=c.id,
                incident_id=c.incident_id,
                event_id=c.event_id,
                correlation_type=CorrelationType(c.correlation_type),
                confidence_score=c.confidence_score,
                reason=c.reason,
                timestamp=incident.started_at,
                service_name=incident.lead_service,
                severity=incident.severity,
                message=incident.title,
            )
            for c in incident.correlations
        ]

        return IncidentDetailResponse(
            id=incident.id,
            incident_id=incident.incident_id,
            title=incident.title,
            description=incident.description,
            status=IncidentStatus(incident.status),
            severity=IncidentSeverity(incident.severity),
            lead_service=incident.lead_service,
            affected_services=incident.affected_services,
            error_signatures=incident.error_signatures,
            started_at=incident.started_at,
            detected_at=incident.detected_at,
            mitigated_at=incident.mitigated_at,
            resolved_at=incident.resolved_at,
            resolved_by=incident.resolved_by,
            resolution_notes=incident.resolution_notes,
            correlated_event_count=len(incident.correlations),
            correlations=correlations,
            timeline=timeline,
            metadata=incident.metadata_ or {},
            created_at=incident.created_at,
            updated_at=incident.updated_at,
        )

    async def update_status(
        self,
        incident_id: str,
        update_data: IncidentStatusUpdate,
    ) -> IncidentResponse:
        """
        Transition incident lifecycle status enforcing state machine rules and
        human approval gates.
        """
        query = select(IncidentModel).where(
            (IncidentModel.id == incident_id) | (IncidentModel.incident_id == incident_id)
        )
        res = await self.db.execute(query)
        incident = res.scalar_one_or_none()

        if incident is None:
            raise EntityNotFoundError(entity="Incident", entity_id=incident_id)

        current_status = IncidentStatus(incident.status)
        new_status, fields_to_update = self.lifecycle_manager.validate_transition(
            current_status=current_status,
            update=update_data,
        )

        incident.status = new_status.value
        incident.updated_at = datetime.now(UTC)

        for key, val in fields_to_update.items():
            setattr(incident, key, val)

        await self.db.commit()
        await self.db.refresh(incident)

        return IncidentResponse(
            id=incident.id,
            incident_id=incident.incident_id,
            title=incident.title,
            description=incident.description,
            status=IncidentStatus(incident.status),
            severity=IncidentSeverity(incident.severity),
            lead_service=incident.lead_service,
            affected_services=incident.affected_services,
            error_signatures=incident.error_signatures,
            started_at=incident.started_at,
            detected_at=incident.detected_at,
            mitigated_at=incident.mitigated_at,
            resolved_at=incident.resolved_at,
            resolved_by=incident.resolved_by,
            resolution_notes=incident.resolution_notes,
            correlated_event_count=0,
            metadata=incident.metadata_ or {},
            created_at=incident.created_at,
            updated_at=incident.updated_at,
        )

    async def get_timeline(self, incident_id: str) -> IncidentTimeline:
        """Generate full chronological timeline for an incident."""
        detail = await self.get_incident(incident_id)
        if detail.timeline is None:
            raise EntityNotFoundError(entity="Timeline for Incident", entity_id=incident_id)
        return detail.timeline
