"""Chronological incident progression timeline generator with milestone markers."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.schemas.anomaly import AnomalyRecord
from app.schemas.incident import (
    IncidentTimeline,
    MilestoneType,
    TimelineMilestone,
)
from app.schemas.log_event import CanonicalLogEvent

logger = logging.getLogger("tracemind.incidents.timeline")


class IncidentTimelineGenerator:
    """
    Constructs an audit-ready, chronological incident timeline highlighting
    root trigger events, cascading degradation, peak impact, and mitigation milestones.
    """

    @staticmethod
    def generate_timeline(
        incident_id: str,
        started_at: datetime,
        detected_at: datetime,
        resolved_at: datetime | None,
        events: list[CanonicalLogEvent],
        anomalies: list[AnomalyRecord] | None = None,
        status_history: list[dict[str, Any]] | None = None,
    ) -> IncidentTimeline:
        """
        Assemble chronological progression from correlated log events and anomalies.
        Strictly sorts all milestones in ascending temporal order.
        """
        milestones: list[TimelineMilestone] = []
        services_set: set[str] = set()

        # 1. Process Log Events
        if events:
            sorted_events = sorted(events, key=lambda e: e.timestamp)
            first_event = sorted_events[0]
            services_set.add(first_event.service_name)

            # Milestone: FIRST_TRIGGER
            milestones.append(
                TimelineMilestone(
                    milestone_id=str(uuid4()),
                    timestamp=first_event.timestamp,
                    milestone_type=MilestoneType.FIRST_TRIGGER,
                    service_name=first_event.service_name,
                    title="Incident Genesis Event",
                    description=(
                        f"First anomalous error detected in '{first_event.service_name}': "
                        f"{first_event.message[:120]}"
                    ),
                    evidence_event_ids=[first_event.event_id],
                    metadata={"severity": first_event.severity},
                )
            )

            # Milestone: ROOT_EXCEPTION (First unhandled exception with stack trace)
            exception_events = [e for e in sorted_events if e.exception_type is not None]
            if exception_events:
                root_exc = exception_events[0]
                milestones.append(
                    TimelineMilestone(
                        milestone_id=str(uuid4()),
                        timestamp=root_exc.timestamp,
                        milestone_type=MilestoneType.ROOT_EXCEPTION,
                        service_name=root_exc.service_name,
                        title=f"Exception Inception: {root_exc.exception_type}",
                        description=f"Initial exception raised in '{root_exc.service_name}': {root_exc.message[:140]}",
                        evidence_event_ids=[root_exc.event_id],
                        metadata={"error_signature": root_exc.error_signature},
                    )
                )

            # Milestone: CASCADE_PROPAGATION (Detection of cascading across secondary services)
            seen_services: set[str] = {first_event.service_name}
            for e in sorted_events:
                services_set.add(e.service_name)
                if e.service_name not in seen_services:
                    seen_services.add(e.service_name)
                    milestones.append(
                        TimelineMilestone(
                            milestone_id=str(uuid4()),
                            timestamp=e.timestamp,
                            milestone_type=MilestoneType.CASCADE_PROPAGATION,
                            service_name=e.service_name,
                            title=f"Cascading Failure: {e.service_name}",
                            description=f"Degradation propagated to downstream service '{e.service_name}'.",
                            evidence_event_ids=[e.event_id],
                            metadata={"originating_service": first_event.service_name},
                        )
                    )

            # Milestone: PEAK_IMPACT (Minute with the highest event concentration)
            minute_buckets: dict[datetime, list[CanonicalLogEvent]] = defaultdict(list)
            for e in sorted_events:
                bucket_key = e.timestamp.replace(second=0, microsecond=0)
                minute_buckets[bucket_key].append(e)

            if minute_buckets:
                peak_time, peak_events = max(minute_buckets.items(), key=lambda item: len(item[1]))
                if len(peak_events) >= 3:
                    milestones.append(
                        TimelineMilestone(
                            milestone_id=str(uuid4()),
                            timestamp=peak_time,
                            milestone_type=MilestoneType.PEAK_IMPACT,
                            service_name=peak_events[0].service_name,
                            title="Peak Error Surge",
                            description=f"Error burst reached peak intensity of {len(peak_events)} errors/minute.",
                            evidence_event_ids=[pe.event_id for pe in peak_events[:5]],
                            metadata={"rate_per_min": len(peak_events)},
                        )
                    )

        # 2. Process Anomalies
        if anomalies:
            for anom in anomalies:
                services_set.add(anom.service_name)
                milestones.append(
                    TimelineMilestone(
                        milestone_id=str(uuid4()),
                        timestamp=anom.timestamp,
                        milestone_type=MilestoneType.FIRST_TRIGGER
                        if not milestones
                        else MilestoneType.CASCADE_PROPAGATION,
                        service_name=anom.service_name,
                        title=f"Statistical Anomaly: {anom.metric_name}",
                        description=(
                            f"Statistical outlier detected by {anom.detection_method.value} "
                            f"(observed: {anom.current_value:.1f}, score: {anom.anomaly_score:.2f})."
                        ),
                        evidence_event_ids=[],
                        metadata={"anomaly_id": anom.anomaly_id, "score": anom.anomaly_score},
                    )
                )

        # 3. Process Status Transitions
        if status_history:
            for item in status_history:
                ts = item.get("timestamp", datetime.now(UTC))
                st = item.get("status")
                actor = item.get("user_id", "Operator")
                notes = item.get("notes", "")

                m_type = (
                    MilestoneType.INVESTIGATION_STARTED
                    if st == "INVESTIGATING"
                    else (
                        MilestoneType.ROOT_CAUSE_IDENTIFIED
                        if st == "IDENTIFIED"
                        else (
                            MilestoneType.MITIGATION_APPLIED
                            if st == "MITIGATED"
                            else (MilestoneType.RESOLVED if st == "RESOLVED" else None)
                        )
                    )
                )

                if m_type is not None:
                    milestones.append(
                        TimelineMilestone(
                            milestone_id=str(uuid4()),
                            timestamp=ts,
                            milestone_type=m_type,
                            service_name=item.get("lead_service", "system"),
                            title=f"Status: {st}",
                            description=f"Transitioned to {st} by {actor}. Notes: {notes}".strip(),
                            evidence_event_ids=[],
                            metadata={"status": st, "user_id": actor},
                        )
                    )

        # 4. Strict chronological ordering
        milestones.sort(key=lambda m: m.timestamp)

        # 5. Calculate overall duration
        end_time = resolved_at or datetime.now(UTC)
        duration_seconds = max(0.0, (end_time - started_at).total_seconds())

        return IncidentTimeline(
            incident_id=incident_id,
            started_at=started_at,
            detected_at=detected_at,
            resolved_at=resolved_at,
            duration_seconds=round(duration_seconds, 1),
            milestones=milestones,
            total_events=len(events),
            services_involved=sorted(services_set),
        )
