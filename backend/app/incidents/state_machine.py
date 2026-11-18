"""Incident lifecycle state machine and human-in-the-loop transition governance."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.core.exceptions import InvalidStateTransitionError
from app.schemas.incident import IncidentSeverity, IncidentStatus, IncidentStatusUpdate

logger = logging.getLogger("tracemind.incidents.lifecycle")

# Explicit permitted state transitions
ALLOWED_TRANSITIONS: dict[IncidentStatus, list[IncidentStatus]] = {
    IncidentStatus.DETECTED: [
        IncidentStatus.INVESTIGATING,
    ],
    IncidentStatus.INVESTIGATING: [
        IncidentStatus.IDENTIFIED,
        IncidentStatus.MITIGATED,  # Quick hotfix during investigation
    ],
    IncidentStatus.IDENTIFIED: [
        IncidentStatus.MITIGATED,
        IncidentStatus.INVESTIGATING,  # Disproved root cause hypothesis
    ],
    IncidentStatus.MITIGATED: [
        IncidentStatus.RESOLVED,
        IncidentStatus.INVESTIGATING,  # Recurrence / failed mitigation
    ],
    IncidentStatus.RESOLVED: [
        IncidentStatus.INVESTIGATING,  # Incident reopened due to recurrence
    ],
}


class IncidentLifecycleManager:
    """
    Enforces valid incident lifecycle transitions and human-in-the-loop approval gates.
    Automated scripts are strictly prohibited from marking incidents as RESOLVED.
    """

    @staticmethod
    def validate_transition(
        current_status: IncidentStatus,
        update: IncidentStatusUpdate,
    ) -> tuple[IncidentStatus, dict[str, str | datetime | None]]:
        """
        Validate whether a state transition is legal according to lifecycle policy.
        Returns the new status and dictionary of timestamp/attribution fields to update.
        Raises InvalidStateTransitionError on illegal transitions.
        """
        target = update.new_status

        # 1. No-op if target status equals current status
        if target == current_status:
            return current_status, {}

        # 2. Check transition validity against state machine rules
        allowed = ALLOWED_TRANSITIONS.get(current_status, [])
        if target not in allowed:
            allowed_names = [s.value for s in allowed]
            raise InvalidStateTransitionError(
                detail=(
                    f"Illegal lifecycle transition: cannot move from '{current_status.value}' "
                    f"to '{target.value}'. Allowed target states: {allowed_names}"
                )
            )

        now = datetime.now(UTC)
        updates: dict[str, str | datetime | None] = {}

        # 3. Enforce Human-in-the-Loop resolution constraints
        if target == IncidentStatus.RESOLVED:
            # Human resolution governance check
            if not update.user_id or update.user_id.lower() in ("system", "bot", "automated"):
                raise InvalidStateTransitionError(
                    detail="Automated machine resolution is prohibited. A verified human user_id is required to resolve incidents."
                )

            if not update.notes and not update.root_cause_summary:
                raise InvalidStateTransitionError(
                    detail="Resolution requires operational notes or a documented root cause summary."
                )

            updates["resolved_at"] = now
            updates["resolved_by"] = update.user_id
            updates["resolution_notes"] = update.notes or update.root_cause_summary

        elif target == IncidentStatus.MITIGATED:
            updates["mitigated_at"] = now

        return target, updates

    @staticmethod
    def calculate_severity(
        error_count: int,
        affected_services_count: int,
        has_critical_exception: bool = False,
        error_rate_multiplier: float = 1.0,
    ) -> IncidentSeverity:
        """
        Compute objective incident severity using operational blast radius and rate deviation.
        """
        if (
            has_critical_exception
            or affected_services_count >= 3
            or error_rate_multiplier >= 5.0
            or error_count >= 100
        ):
            return IncidentSeverity.CRITICAL

        if affected_services_count >= 2 or error_rate_multiplier >= 3.0 or error_count >= 25:
            return IncidentSeverity.HIGH

        if error_rate_multiplier >= 1.5 or error_count >= 5:
            return IncidentSeverity.MEDIUM

        return IncidentSeverity.LOW
