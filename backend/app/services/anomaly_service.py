"""Service layer for statistical anomaly detection, baseline fetching, and persistence."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import desc, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly_detection.baseline import HistoricalBaselineCalculator
from app.anomaly_detection.statistical import (
    CompositeAnomalyDetector,
    IQRDetector,
    IsolationForestDetector,
    ZScoreDetector,
)
from app.models.anomaly import AnomalyModel
from app.schemas.anomaly import (
    AnomalyDetectionRequest,
    AnomalyRecord,
    DetectionMethod,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

    RedisClient = Redis[str]
else:
    RedisClient = Any

logger = logging.getLogger("tracemind.services.anomaly")


class AnomalyService:
    """
    Orchestrates statistical anomaly detection over streaming telemetry and logs,
    caches baseline metrics, and persists identified anomalies into PostgreSQL.
    """

    def __init__(self, db: AsyncSession, redis_client: RedisClient | None = None) -> None:
        self.db = db
        self.redis = redis_client
        self.baseline_calc = HistoricalBaselineCalculator(redis_client=redis_client)

    async def detect_and_record_anomalies(
        self,
        request: AnomalyDetectionRequest,
    ) -> list[AnomalyRecord]:
        """
        Run statistical anomaly detection over requested time-series data points,
        evaluate against the service's baseline, and persist flagged anomalies.
        """
        # 1. Fetch or compute historical baseline
        values = [pt.value for pt in request.data_points]
        baseline = await self.baseline_calc.get_or_create_service_baseline(
            service_name=request.service_name,
            metric_name=request.metric_name,
            fallback_series=values,
        )

        # 2. Select detection algorithm
        detected: list[AnomalyRecord] = []
        if request.method == DetectionMethod.Z_SCORE:
            detector = ZScoreDetector(threshold=3.0 * request.sensitivity)
            detected = detector.detect(request.data_points, baseline)
        elif request.method == DetectionMethod.IQR:
            detector_iqr = IQRDetector(k=1.5 * request.sensitivity)
            detected = detector_iqr.detect(request.data_points, baseline)
        elif request.method == DetectionMethod.ISOLATION_FOREST:
            detector_if = IsolationForestDetector()
            detected = detector_if.detect(request.data_points, baseline)
        else:
            # Composite / Ensemble (Default)
            composite = CompositeAnomalyDetector(
                z_threshold=3.0 * request.sensitivity,
                iqr_k=1.5 * request.sensitivity,
            )
            detected = composite.detect(request.data_points, baseline)

        # 3. Persist detected anomalies to database
        if detected:
            await self._persist_anomalies(detected)

        return detected

    async def _persist_anomalies(self, anomalies: list[AnomalyRecord]) -> None:
        """Persist anomaly records into PostgreSQL."""
        records = [
            {
                "id": str(uuid4()),
                "anomaly_id": a.anomaly_id,
                "service_name": a.service_name,
                "timestamp": a.timestamp,
                "metric_name": a.metric_name,
                "current_value": a.current_value,
                "baseline_mean": a.baseline_mean,
                "baseline_std": a.baseline_std,
                "threshold": a.threshold,
                "anomaly_score": a.anomaly_score,
                "severity": a.severity.value,
                "detection_method": a.detection_method.value,
                "details": a.details,
                "incident_id": a.incident_id,
                "created_at": datetime.now(UTC),
            }
            for a in anomalies
        ]

        stmt = insert(AnomalyModel).values(records)
        await self.db.execute(stmt)
        await self.db.commit()

    async def list_anomalies(
        self,
        service_name: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AnomalyRecord], int]:
        """Query stored anomalies with filtering and pagination."""
        base_query = select(AnomalyModel)
        count_query = select(func.count()).select_from(AnomalyModel)

        filters = []
        if service_name:
            filters.append(AnomalyModel.service_name == service_name)
        if severity:
            filters.append(AnomalyModel.severity == severity)

        if filters:
            base_query = base_query.where(*filters)
            count_query = count_query.where(*filters)

        total_res = await self.db.execute(count_query)
        total = total_res.scalar() or 0

        paginated_query = (
            base_query.order_by(desc(AnomalyModel.timestamp)).limit(limit).offset(offset)
        )
        res = await self.db.execute(paginated_query)
        rows = res.scalars().all()

        records = [
            AnomalyRecord(
                anomaly_id=r.anomaly_id,
                service_name=r.service_name,
                timestamp=r.timestamp,
                metric_name=r.metric_name,
                current_value=r.current_value,
                baseline_mean=r.baseline_mean,
                baseline_std=r.baseline_std,
                threshold=r.threshold,
                anomaly_score=r.anomaly_score,
                severity=r.severity,  # type: ignore[arg-type]
                detection_method=r.detection_method,  # type: ignore[arg-type]
                confidence=0.9,
                details=r.details,
                incident_id=r.incident_id,
                created_at=r.created_at,
            )
            for r in rows
        ]
        return records, total
