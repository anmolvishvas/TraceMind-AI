"""create incidents and anomalies tables

Revision ID: 0003_incidents_anomalies
Revises: 0002_log_events
Create Date: 2026-11-18 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_incidents_anomalies"
down_revision: str | None = "0002_log_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the incidents, incident_correlations, and anomalies tables."""
    # 1. Incidents table
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("incident_id", sa.String(length=64), unique=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DETECTED"),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="MEDIUM"),
        sa.Column("lead_service", sa.String(length=128), nullable=False),
        sa.Column(
            "affected_services",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "error_signatures",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mitigated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=128), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incidents_incident_id", "incidents", ["incident_id"], unique=True)
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_lead_service", "incidents", ["lead_service"])
    op.create_index("ix_incidents_started_at", "incidents", ["started_at"])
    op.create_index("ix_incidents_status_severity", "incidents", ["status", "severity"])
    op.create_index(
        "ix_incidents_lead_service_started", "incidents", ["lead_service", "started_at"]
    )

    # 2. Incident Correlations table
    op.create_table(
        "incident_correlations",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "incident_id",
            sa.String(length=36),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column(
            "correlation_type",
            sa.String(length=32),
            nullable=False,
            server_default="TEMPORAL_SERVICE",
        ),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_incident_correlations_incident_id", "incident_correlations", ["incident_id"]
    )
    op.create_index("ix_incident_correlations_event_id", "incident_correlations", ["event_id"])
    op.create_index(
        "ix_incident_correlations_incident_event",
        "incident_correlations",
        ["incident_id", "event_id"],
    )

    # 3. Anomalies table
    op.create_table(
        "anomalies",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("anomaly_id", sa.String(length=64), unique=True, nullable=False),
        sa.Column("service_name", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("baseline_mean", sa.Float(), nullable=True),
        sa.Column("baseline_std", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("detection_method", sa.String(length=32), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("incident_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_anomalies_anomaly_id", "anomalies", ["anomaly_id"], unique=True)
    op.create_index("ix_anomalies_service_name", "anomalies", ["service_name"])
    op.create_index("ix_anomalies_timestamp", "anomalies", ["timestamp"])
    op.create_index("ix_anomalies_severity", "anomalies", ["severity"])
    op.create_index("ix_anomalies_incident_id", "anomalies", ["incident_id"])
    op.create_index("ix_anomalies_service_timestamp", "anomalies", ["service_name", "timestamp"])
    op.create_index("ix_anomalies_severity_timestamp", "anomalies", ["severity", "timestamp"])


def downgrade() -> None:
    """Drop the anomalies, incident_correlations, and incidents tables."""
    op.drop_table("anomalies")
    op.drop_table("incident_correlations")
    op.drop_table("incidents")
