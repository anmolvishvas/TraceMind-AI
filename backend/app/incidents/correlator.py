"""Multi-dimensional incident correlation engine clustering distributed operational events."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta
from uuid import uuid4

from app.schemas.incident import (
    CorrelationType,
    IncidentCreate,
    IncidentEventCorrelation,
    IncidentSeverity,
)
from app.schemas.log_event import CanonicalLogEvent

logger = logging.getLogger("tracemind.incidents.correlator")

# Default service dependency topology for microservices cascading failure detection
DEFAULT_SERVICE_TOPOLOGY: dict[str, list[str]] = {
    "api-gateway": ["auth-service", "order-service", "payment-service", "user-service"],
    "order-service": ["inventory-service", "payment-service", "database", "postgres"],
    "payment-service": ["stripe-adapter", "database", "redis", "postgres"],
    "auth-service": ["database", "redis", "user-service", "postgres"],
    "notification-service": ["redis", "kafka", "email-gateway"],
}


class IncidentCorrelator:
    """
    Correlates disparate log events and anomalies across temporal windows,
    distributed trace IDs, error signatures, and service dependency topology.
    """

    def __init__(
        self,
        temporal_window_seconds: int = 300,  # 5 minutes
        topology: dict[str, list[str]] | None = None,
    ) -> None:
        self.window_delta = timedelta(seconds=temporal_window_seconds)
        self.topology = topology or DEFAULT_SERVICE_TOPOLOGY

    def correlate_events(
        self,
        events: list[CanonicalLogEvent],
    ) -> list[tuple[IncidentCreate, list[IncidentEventCorrelation]]]:
        """
        Group unassigned log events into cohesive incident clusters.
        Filters for ERROR or CRITICAL events as incident candidates.
        """
        if not events:
            return []

        # Filter for operational errors and exceptions
        error_events = [
            e for e in events if e.severity in ("ERROR", "CRITICAL") or e.exception_type is not None
        ]

        if not error_events:
            return []

        # Sort strictly by timestamp ascending
        sorted_events = sorted(error_events, key=lambda e: e.timestamp)

        # 1. Group by Trace ID / Request ID (Confirmed Causal links)
        trace_groups: dict[str, list[CanonicalLogEvent]] = defaultdict(list)
        untraced_events: list[CanonicalLogEvent] = []

        for e in sorted_events:
            trace_key = e.trace_id or e.request_id
            if trace_key:
                trace_groups[trace_key].append(e)
            else:
                untraced_events.append(e)

        incident_candidates: list[tuple[IncidentCreate, list[IncidentEventCorrelation]]] = []

        # 2. Form incidents from confirmed trace groups
        for trace_id, trace_evts in trace_groups.items():
            if len(trace_evts) >= 1:
                incident, correlations = self._build_incident_from_group(
                    events=trace_evts,
                    primary_correlation_type=CorrelationType.CONFIRMED_CAUSAL,
                    reason=f"Correlated by distributed trace ID: {trace_id}",
                    confidence=1.0,
                )
                incident_candidates.append((incident, correlations))

        # 3. Cluster remaining untraced events by sliding temporal window + service topology
        temporal_clusters: list[list[CanonicalLogEvent]] = []
        for e in untraced_events:
            added_to_cluster = False
            for cluster in temporal_clusters:
                last_event = cluster[-1]
                # Check if within temporal window
                if (
                    abs((e.timestamp - last_event.timestamp).total_seconds())
                    <= self.window_delta.total_seconds()
                ):
                    # Check service relation or matching error signature
                    if (
                        e.service_name == last_event.service_name
                        or self._are_services_related(e.service_name, last_event.service_name)
                        or (e.error_signature and e.error_signature == last_event.error_signature)
                    ):
                        cluster.append(e)
                        added_to_cluster = True
                        break

            if not added_to_cluster:
                temporal_clusters.append([e])

        # 4. Form incidents from temporal clusters
        for cluster in temporal_clusters:
            # Determine correlation type
            first_sig = cluster[0].error_signature
            all_same_sig = first_sig is not None and all(
                e.error_signature == first_sig for e in cluster
            )

            services = {e.service_name for e in cluster}
            if all_same_sig and len(cluster) > 1 and first_sig:
                corr_type = CorrelationType.SIGNATURE_BURST
                reason = f"Burst of identical error signature: {first_sig[:12]}..."
                confidence = 0.92
            elif len(services) > 1:
                corr_type = CorrelationType.CASCADING_FAILURE
                reason = f"Cascading degradation across services: {', '.join(services)}"
                confidence = 0.85
            else:
                corr_type = CorrelationType.TEMPORAL_SERVICE
                reason = f"Elevated error frequency in {cluster[0].service_name}"
                confidence = 0.80

            incident, correlations = self._build_incident_from_group(
                events=cluster,
                primary_correlation_type=corr_type,
                reason=reason,
                confidence=confidence,
            )
            incident_candidates.append((incident, correlations))

        return incident_candidates

    def _are_services_related(self, service_a: str, service_b: str) -> bool:
        """Check if two services share a direct dependency edge in topology."""
        if service_a == service_b:
            return True
        deps_a = self.topology.get(service_a, [])
        deps_b = self.topology.get(service_b, [])
        return (service_b in deps_a) or (service_a in deps_b)

    def _build_incident_from_group(
        self,
        events: list[CanonicalLogEvent],
        primary_correlation_type: CorrelationType,
        reason: str,
        confidence: float,
    ) -> tuple[IncidentCreate, list[IncidentEventCorrelation]]:
        """Synthesize an IncidentCreate schema and correlation link list from an event group."""
        sorted_evts = sorted(events, key=lambda e: e.timestamp)
        earliest_event = sorted_evts[0]
        incident_id = f"inc-{uuid4().hex[:10]}"

        # Collect affected services and error signatures
        affected_services = sorted({e.service_name for e in sorted_evts})
        error_signatures = sorted(
            {e.error_signature for e in sorted_evts if e.error_signature is not None}
        )

        lead_service = earliest_event.service_name
        title = self._generate_incident_title(lead_service, sorted_evts)

        # Dynamic severity classification
        severity = self._compute_severity(sorted_evts, affected_services)

        correlations: list[IncidentEventCorrelation] = []
        for e in sorted_evts:
            corr = IncidentEventCorrelation(
                correlation_id=str(uuid4()),
                incident_id=incident_id,
                event_id=e.event_id,
                correlation_type=primary_correlation_type,
                confidence_score=confidence,
                reason=reason,
                timestamp=e.timestamp,
                service_name=e.service_name,
                severity=e.severity,
                message=e.message,
                error_signature=e.error_signature,
                trace_id=e.trace_id,
            )
            correlations.append(corr)

        incident_create = IncidentCreate(
            title=title,
            description=f"Correlated {len(sorted_evts)} events across {len(affected_services)} services. Reason: {reason}",
            lead_service=lead_service,
            severity=severity,
            affected_services=affected_services,
            error_signatures=error_signatures,
            started_at=earliest_event.timestamp,
            detected_at=sorted_evts[-1].timestamp,
            metadata={
                "event_count": len(sorted_evts),
                "correlation_type": primary_correlation_type.value,
                "confidence_score": confidence,
            },
        )

        return incident_create, correlations

    def _generate_incident_title(
        self,
        lead_service: str,
        events: list[CanonicalLogEvent],
    ) -> str:
        """Create a clear, human-readable operational incident title."""
        exception_types = [e.exception_type for e in events if e.exception_type]
        if exception_types:
            top_exception = exception_types[0]
            return f"[{lead_service}] Recurring {top_exception} incident"
        return f"[{lead_service}] Operational error spike detected"

    def _compute_severity(
        self,
        events: list[CanonicalLogEvent],
        affected_services: list[str],
    ) -> IncidentSeverity:
        """Dynamically compute incident severity based on error volume and blast radius."""
        has_critical = any(e.severity == "CRITICAL" for e in events)
        event_count = len(events)
        service_count = len(affected_services)

        if has_critical or service_count >= 3 or event_count >= 50:
            return IncidentSeverity.CRITICAL
        if service_count >= 2 or event_count >= 15:
            return IncidentSeverity.HIGH
        if event_count >= 5:
            return IncidentSeverity.MEDIUM
        return IncidentSeverity.LOW
