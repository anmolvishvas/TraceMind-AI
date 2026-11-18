"""Master v1 API Router."""

from fastapi import APIRouter

from app.api.v1.endpoints import anomalies, health, incidents, logs

api_v1_router = APIRouter()

# Mount health & readiness endpoints
api_v1_router.include_router(health.router, prefix="/health", tags=["Health"])

# Mount log ingestion and search endpoints
api_v1_router.include_router(logs.router)

# Mount statistical anomaly detection endpoints
api_v1_router.include_router(anomalies.router)

# Mount incident correlation and lifecycle endpoints
api_v1_router.include_router(incidents.router)
