from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.redis import close_redis


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    project: str
    version: str
    environment: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifecycle context manager for resource initialization and teardown."""
    # Startup hooks
    yield
    # Shutdown hooks: gracefully release Redis client pool
    await close_redis()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Production-grade AI-powered incident intelligence and RCA platform.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Liveness probe (root level)
    @application.get("/healthz", response_model=HealthResponse, tags=["Health"])
    async def healthcheck() -> dict[str, Any]:
        """Liveness probe verifying the API gateway process is running."""
        return {
            "status": "healthy",
            "project": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        }

    # Mount API v1 router
    application.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return application


app = create_app()
