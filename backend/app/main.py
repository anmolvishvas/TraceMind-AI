from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import EntityNotFoundError, InvalidStateTransitionError
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

    @application.exception_handler(EntityNotFoundError)
    async def entity_not_found_handler(request: Request, exc: EntityNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": exc.message, "details": exc.details},
        )

    @application.exception_handler(InvalidStateTransitionError)
    async def invalid_transition_handler(
        request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": exc.detail, "details": exc.details},
        )

    return application


app = create_app()
