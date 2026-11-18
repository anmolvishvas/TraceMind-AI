"""SQLAlchemy 2.0 ORM model for detected statistical anomalies."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnomalyModel(Base):
    """
    SQLAlchemy ORM model storing detected statistical anomalies and outliers.
    """

    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        nullable=False,
    )
    anomaly_id: Mapped[str] = mapped_column(
        sa.String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    service_name: Mapped[str] = mapped_column(
        sa.String(128),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
    )
    current_value: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
    )
    baseline_mean: Mapped[float | None] = mapped_column(
        sa.Float,
        nullable=True,
    )
    baseline_std: Mapped[float | None] = mapped_column(
        sa.Float,
        nullable=True,
    )
    threshold: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
    )
    anomaly_score: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        index=True,
    )
    detection_method: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )
    incident_id: Mapped[str | None] = mapped_column(
        sa.String(36),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        sa.Index("ix_anomalies_service_timestamp", "service_name", "timestamp"),
        sa.Index("ix_anomalies_severity_timestamp", "severity", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<AnomalyModel(id={self.id}, anomaly_id={self.anomaly_id}, "
            f"service={self.service_name}, score={self.anomaly_score:.2f}, severity={self.severity})>"
        )
