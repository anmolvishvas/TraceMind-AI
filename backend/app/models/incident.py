"""SQLAlchemy 2.0 ORM models for incidents and event correlations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class IncidentModel(Base):
    """
    SQLAlchemy ORM model representing an operational incident cluster.
    """

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        nullable=False,
    )
    incident_id: Mapped[str] = mapped_column(
        sa.String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="DETECTED",
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="MEDIUM",
        index=True,
    )
    lead_service: Mapped[str] = mapped_column(
        sa.String(128),
        nullable=False,
        index=True,
    )
    affected_services: Mapped[list[str]] = mapped_column(
        postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
        nullable=False,
        default=list,
    )
    error_signatures: Mapped[list[str]] = mapped_column(
        postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
        nullable=False,
        default=list,
    )
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
    mitigated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[str | None] = mapped_column(
        sa.String(128),
        nullable=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    correlations: Mapped[list[IncidentCorrelationModel]] = relationship(
        "IncidentCorrelationModel",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentCorrelationModel.created_at",
    )

    __table_args__ = (
        sa.Index("ix_incidents_status_severity", "status", "severity"),
        sa.Index("ix_incidents_lead_service_started", "lead_service", "started_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentModel(id={self.id}, incident_id={self.incident_id}, "
            f"service={self.lead_service}, status={self.status}, severity={self.severity})>"
        )


class IncidentCorrelationModel(Base):
    """
    SQLAlchemy ORM model linking specific log events / anomalies to an incident.
    """

    __tablename__ = "incident_correlations"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        nullable=False,
    )
    incident_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        index=True,
    )
    correlation_type: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="TEMPORAL_SERVICE",
    )
    confidence_score: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
        default=1.0,
    )
    reason: Mapped[str | None] = mapped_column(
        sa.String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    incident: Mapped[IncidentModel] = relationship(
        "IncidentModel",
        back_populates="correlations",
    )

    __table_args__ = (
        sa.Index("ix_incident_correlations_event", "event_id"),
        sa.Index("ix_incident_correlations_incident_event", "incident_id", "event_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentCorrelationModel(incident_id={self.incident_id}, "
            f"event_id={self.event_id}, type={self.correlation_type})>"
        )
