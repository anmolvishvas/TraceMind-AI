"""Pydantic schemas for statistical anomaly detection and baseline metrics."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class DetectionMethod(StrEnum):
    """Statistical detection algorithms supported by TraceMind AI."""

    Z_SCORE = "Z_SCORE"
    IQR = "IQR"
    ISOLATION_FOREST = "ISOLATION_FOREST"
    ENSEMBLE = "ENSEMBLE"


class AnomalySeverity(StrEnum):
    """Severity classification for statistical anomalies."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyType(StrEnum):
    """Morphological classification of operational anomalies."""

    SPIKE = "SPIKE"
    STEP_CHANGE = "STEP_CHANGE"
    ERROR_BURST = "ERROR_BURST"
    LATENCY_DEGRADATION = "LATENCY_DEGRADATION"
    UNKNOWN = "UNKNOWN"


class ServiceBaseline(BaseModel):
    """Statistical profile representing normal traffic and error parameters for a service."""

    service_name: str = Field(..., description="Service identifier")
    metric_name: str = Field("error_rate", description="Metric represented by this baseline")
    window_hours: int = Field(
        168, description="Historical lookback window in hours (default 7 days)"
    )
    mean: float = Field(..., ge=0.0, description="Baseline sample mean")
    std_dev: float = Field(..., ge=0.0, description="Baseline sample standard deviation")
    median: float = Field(..., ge=0.0, description="Median metric value")
    iqr: float = Field(..., ge=0.0, description="Interquartile range (Q3 - Q1)")
    q1: float = Field(..., ge=0.0, description="First quartile (25th percentile)")
    q3: float = Field(..., ge=0.0, description="Third quartile (75th percentile)")
    sample_size: int = Field(..., ge=0, description="Number of historical observation points")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MetricDataPoint(BaseModel):
    """Individual time-series observation for anomaly detection."""

    timestamp: datetime = Field(..., description="Observation timestamp in UTC")
    value: float = Field(..., description="Numerical metric value (e.g. error count, latency ms)")
    service_name: str = Field(..., description="Originating service name")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Contextual dimensions")


class AnomalyRecord(BaseModel):
    """Structured result produced when an operational anomaly is detected."""

    anomaly_id: str = Field(default_factory=lambda: f"anom-{uuid4().hex[:12]}")
    service_name: str = Field(..., description="Affected service identifier")
    timestamp: datetime = Field(..., description="UTC timestamp when anomaly occurred")
    metric_name: str = Field(..., description="Observed metric")
    current_value: float = Field(..., description="Actual observed metric value")
    baseline_mean: float | None = Field(default=None, description="Expected baseline mean value")
    baseline_std: float | None = Field(
        default=None, description="Expected baseline standard deviation"
    )
    threshold: float = Field(..., description="Detection threshold exceeded")
    anomaly_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized anomaly score between 0.0 (normal) and 1.0 (severe outlier)",
    )
    severity: AnomalySeverity = Field(..., description="Classified severity level")
    anomaly_type: AnomalyType = Field(default=AnomalyType.SPIKE, description="Pattern morphology")
    detection_method: DetectionMethod = Field(..., description="Algorithm that flagged the anomaly")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Statistical confidence level of detection"
    )
    details: dict[str, Any] = Field(default_factory=dict, description="Diagnostic telemetry")
    incident_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AnomalyDetectionRequest(BaseModel):
    """Request payload to trigger statistical anomaly detection across a time-series."""

    service_name: str = Field(..., description="Service to analyze")
    metric_name: str = Field("error_count", description="Metric to evaluate")
    data_points: list[MetricDataPoint] = Field(
        ..., min_length=3, description="Chronological time-series observations"
    )
    method: DetectionMethod = Field(
        default=DetectionMethod.ENSEMBLE, description="Target statistical algorithm"
    )
    sensitivity: float = Field(
        default=1.0,
        ge=0.1,
        le=3.0,
        description="Sensitivity multiplier (1.0 = standard 3-sigma / 1.5 IQR)",
    )
