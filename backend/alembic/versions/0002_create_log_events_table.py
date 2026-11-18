"""create log_events table and indexes

Revision ID: 0002_log_events
Revises: 0001_pgvector
Create Date: 2026-11-18 12:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_log_events"
down_revision: str | None = "0001_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the log_events table with optimized time-series indices."""
    op.create_table(
        "log_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), unique=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("service_name", sa.String(length=100), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False, server_default="production"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("exception_type", sa.String(length=256), nullable=True),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("error_signature", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("span_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("source_file", sa.String(length=256), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_log_events_event_id", "log_events", ["event_id"])
    op.create_index("ix_log_events_timestamp", "log_events", ["timestamp"])
    op.create_index("ix_log_events_severity", "log_events", ["severity"])
    op.create_index("ix_log_events_service_name", "log_events", ["service_name"])
    op.create_index("ix_log_events_environment", "log_events", ["environment"])
    op.create_index("ix_log_events_exception_type", "log_events", ["exception_type"])
    op.create_index("ix_log_events_error_signature", "log_events", ["error_signature"])
    op.create_index("ix_log_events_request_id", "log_events", ["request_id"])
    op.create_index("ix_log_events_trace_id", "log_events", ["trace_id"])
    op.create_index("ix_log_events_correlation_id", "log_events", ["correlation_id"])

    # Composite indexes
    op.create_index("ix_log_events_service_timestamp", "log_events", ["service_name", "timestamp"])
    op.create_index(
        "ix_log_events_signature_timestamp", "log_events", ["error_signature", "timestamp"]
    )
    op.create_index("ix_log_events_severity_timestamp", "log_events", ["severity", "timestamp"])
    op.create_index("ix_log_events_env_service", "log_events", ["environment", "service_name"])


def downgrade() -> None:
    """Drop the log_events table and all associated indexes."""
    op.drop_index("ix_log_events_env_service", table_name="log_events")
    op.drop_index("ix_log_events_severity_timestamp", table_name="log_events")
    op.drop_index("ix_log_events_signature_timestamp", table_name="log_events")
    op.drop_index("ix_log_events_service_timestamp", table_name="log_events")
    op.drop_index("ix_log_events_correlation_id", table_name="log_events")
    op.drop_index("ix_log_events_trace_id", table_name="log_events")
    op.drop_index("ix_log_events_request_id", table_name="log_events")
    op.drop_index("ix_log_events_error_signature", table_name="log_events")
    op.drop_index("ix_log_events_exception_type", table_name="log_events")
    op.drop_index("ix_log_events_environment", table_name="log_events")
    op.drop_index("ix_log_events_service_name", table_name="log_events")
    op.drop_index("ix_log_events_severity", table_name="log_events")
    op.drop_index("ix_log_events_timestamp", table_name="log_events")
    op.drop_index("ix_log_events_event_id", table_name="log_events")
    op.drop_table("log_events")
