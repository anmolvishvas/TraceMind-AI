"""Unit tests for IncidentLifecycleManager and state machine transitions."""

import pytest

from app.core.exceptions import InvalidStateTransitionError
from app.incidents.state_machine import IncidentLifecycleManager
from app.schemas.incident import IncidentSeverity, IncidentStatus, IncidentStatusUpdate


def test_legal_lifecycle_transitions() -> None:
    """Verify happy-path lifecycle progression from DETECTED to RESOLVED."""
    mgr = IncidentLifecycleManager()

    # DETECTED -> INVESTIGATING
    st, upd = mgr.validate_transition(
        current_status=IncidentStatus.DETECTED,
        update=IncidentStatusUpdate(
            new_status=IncidentStatus.INVESTIGATING, user_id="alice@tracemind.ai"
        ),
    )
    assert st == IncidentStatus.INVESTIGATING

    # INVESTIGATING -> IDENTIFIED
    st, upd = mgr.validate_transition(
        current_status=IncidentStatus.INVESTIGATING,
        update=IncidentStatusUpdate(
            new_status=IncidentStatus.IDENTIFIED,
            user_id="alice@tracemind.ai",
            root_cause_summary="Deadlock in payment gateway database",
        ),
    )
    assert st == IncidentStatus.IDENTIFIED

    # IDENTIFIED -> MITIGATED
    st, upd = mgr.validate_transition(
        current_status=IncidentStatus.IDENTIFIED,
        update=IncidentStatusUpdate(
            new_status=IncidentStatus.MITIGATED,
            user_id="bob@tracemind.ai",
            remediation_action="Restarted DB connection pool",
        ),
    )
    assert st == IncidentStatus.MITIGATED
    assert "mitigated_at" in upd

    # MITIGATED -> RESOLVED (Human verified)
    st, upd = mgr.validate_transition(
        current_status=IncidentStatus.MITIGATED,
        update=IncidentStatusUpdate(
            new_status=IncidentStatus.RESOLVED,
            user_id="lead-sre@tracemind.ai",
            notes="Post-incident verification complete. Error rates nominal.",
        ),
    )
    assert st == IncidentStatus.RESOLVED
    assert upd["resolved_by"] == "lead-sre@tracemind.ai"
    assert "resolved_at" in upd


def test_illegal_jump_to_resolved_blocked() -> None:
    """Verify cannot transition directly from DETECTED to RESOLVED."""
    mgr = IncidentLifecycleManager()
    with pytest.raises(InvalidStateTransitionError, match="Illegal lifecycle transition"):
        mgr.validate_transition(
            current_status=IncidentStatus.DETECTED,
            update=IncidentStatusUpdate(
                new_status=IncidentStatus.RESOLVED,
                user_id="operator@tracemind.ai",
                notes="Skipping ahead",
            ),
        )


def test_automated_machine_resolution_blocked() -> None:
    """Verify that bots or automated systems cannot resolve incidents without a human."""
    mgr = IncidentLifecycleManager()

    # Disallow 'bot'
    with pytest.raises(
        InvalidStateTransitionError, match="Automated machine resolution is prohibited"
    ):
        mgr.validate_transition(
            current_status=IncidentStatus.MITIGATED,
            update=IncidentStatusUpdate(
                new_status=IncidentStatus.RESOLVED,
                user_id="bot",
                notes="Automated clean-up",
            ),
        )

    # Disallow 'system'
    with pytest.raises(
        InvalidStateTransitionError, match="Automated machine resolution is prohibited"
    ):
        mgr.validate_transition(
            current_status=IncidentStatus.MITIGATED,
            update=IncidentStatusUpdate(
                new_status=IncidentStatus.RESOLVED,
                user_id="system",
                notes="Script run",
            ),
        )


def test_resolution_requires_notes() -> None:
    """Verify that resolving an incident requires documentation/notes."""
    mgr = IncidentLifecycleManager()
    with pytest.raises(InvalidStateTransitionError, match="Resolution requires operational notes"):
        mgr.validate_transition(
            current_status=IncidentStatus.MITIGATED,
            update=IncidentStatusUpdate(
                new_status=IncidentStatus.RESOLVED,
                user_id="sre@tracemind.ai",
                notes=None,
            ),
        )


def test_calculate_severity_rules() -> None:
    """Verify dynamic severity scoring rules."""
    mgr = IncidentLifecycleManager()

    # Critical: critical exception or >= 3 services or >= 5x multiplier
    assert mgr.calculate_severity(10, 3) == IncidentSeverity.CRITICAL
    assert mgr.calculate_severity(10, 1, has_critical_exception=True) == IncidentSeverity.CRITICAL
    assert mgr.calculate_severity(10, 1, error_rate_multiplier=5.5) == IncidentSeverity.CRITICAL

    # High: 2 services or >= 3x multiplier
    assert mgr.calculate_severity(10, 2) == IncidentSeverity.HIGH
    assert mgr.calculate_severity(10, 1, error_rate_multiplier=3.2) == IncidentSeverity.HIGH

    # Medium: >= 5 errors or >= 1.5x
    assert mgr.calculate_severity(6, 1) == IncidentSeverity.MEDIUM

    # Low
    assert mgr.calculate_severity(2, 1) == IncidentSeverity.LOW
