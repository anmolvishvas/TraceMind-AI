from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import check_database_health
from app.core.redis import check_redis_health

router = APIRouter()
settings = get_settings()


class SubsystemHealth(BaseModel):
    """Subsystem status details."""

    status: str
    connected: bool
    details: dict[str, Any] | None = None


class ReadinessResponse(BaseModel):
    """Readiness probe response schema."""

    status: str
    project: str
    version: str
    environment: str
    database: dict[str, Any]
    redis: dict[str, Any]


@router.get("/readyz", response_model=ReadinessResponse, tags=["Health"])
async def readiness_probe() -> JSONResponse:
    """
    Readiness probe validating external dependencies (PostgreSQL + pgvector and Redis).
    Returns HTTP 200 when ready, HTTP 503 when dependencies are unhealthy.
    """
    db_health = await check_database_health()
    redis_health = await check_redis_health()

    is_ready = db_health.get("connected", False) and redis_health.get("connected", False)

    payload = {
        "status": "ready" if is_ready else "not_ready",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_health,
        "redis": redis_health,
    }

    http_status = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=http_status, content=payload)
