"""REST API endpoints for statistical anomaly detection and metric analysis."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_redis
from app.schemas.anomaly import AnomalyDetectionRequest, AnomalyRecord
from app.services.anomaly_service import AnomalyService

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.post("/detect", response_model=list[AnomalyRecord], status_code=200)
async def detect_anomalies(
    request: AnomalyDetectionRequest,
    db: AsyncSession = Depends(get_db_session),
    redis: Any = Depends(get_redis),
) -> list[AnomalyRecord]:
    """
    Run pure Python/Scikit-learn statistical anomaly detection over a time-series.
    Evaluates data points against the historical baseline using Z-Score, IQR,
    Isolation Forest, or an Ensemble voting consensus.
    """
    service = AnomalyService(db=db, redis_client=redis)
    return await service.detect_and_record_anomalies(request)


@router.get("", response_model=dict[str, Any], status_code=200)
async def list_anomalies(
    service_name: str | None = Query(None, description="Filter by service"),
    severity: str | None = Query(
        None, description="Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)"
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve indexed statistical anomalies with filtering and pagination."""
    service = AnomalyService(db=db)
    items, total = await service.list_anomalies(
        service_name=service_name,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [item.model_dump() for item in items],
    }
