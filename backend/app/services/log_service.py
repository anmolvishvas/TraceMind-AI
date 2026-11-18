"""Service for high-throughput log persistence and real-time operational metrics."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import desc, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log_event import LogEventModel
from app.schemas.log_event import CanonicalLogEvent

if TYPE_CHECKING:
    from redis.asyncio import Redis

    RedisClient = Redis[str]
else:
    RedisClient = Any

logger = logging.getLogger("tracemind.services.log")

BATCH_SIZE = 500


class IngestionResult(BaseModel):
    """Structured report returned upon completing log file ingestion."""

    ingestion_id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    total_parsed: int
    errors_detected: int
    service_breakdown: dict[str, int]
    severity_breakdown: dict[str, int]
    duration_ms: float


class LogService:
    """
    Log persistence engine executing micro-batched multi-row inserts into PostgreSQL
    and updating Redis rolling metric counters atomically.
    """

    def __init__(self, db: AsyncSession, redis_client: RedisClient | None = None) -> None:
        self.db = db
        self.redis = redis_client

    async def persist_batch(self, events: list[CanonicalLogEvent]) -> int:
        """
        Persist a micro-batch of canonical events to the database and update metrics.
        """
        if not events:
            return 0

        # 1. Prepare dictionary records for bulk insert
        records = [
            {
                "id": str(uuid4()),
                "event_id": e.event_id,
                "timestamp": e.timestamp,
                "severity": e.severity,
                "service_name": e.service_name,
                "environment": e.environment,
                "message": e.message,
                "exception_type": e.exception_type,
                "stack_trace": e.stack_trace,
                "error_signature": e.error_signature,
                "request_id": e.request_id,
                "trace_id": e.trace_id,
                "span_id": e.span_id,
                "correlation_id": e.correlation_id,
                "source_file": e.source_file,
                "line_number": e.line_number,
                "attributes": e.metadata,
                "created_at": datetime.now(UTC),
            }
            for e in events
        ]

        stmt = insert(LogEventModel).values(records)
        await self.db.execute(stmt)
        await self.db.commit()

        # 2. Update Redis metrics asynchronously
        if self.redis is not None:
            await self._update_redis_metrics(events)

        return len(events)

    async def ingest_stream(
        self,
        event_stream: AsyncIterator[CanonicalLogEvent],
        filename: str,
    ) -> IngestionResult:
        """
        Stream events into bounded micro-batches and persist them continuously.
        """
        start_time = datetime.now(UTC)
        total_parsed = 0
        errors_detected = 0
        service_counts: dict[str, int] = defaultdict(int)
        severity_counts: dict[str, int] = defaultdict(int)

        batch: list[CanonicalLogEvent] = []

        async for event in event_stream:
            total_parsed += 1
            service_counts[event.service_name] += 1
            severity_counts[event.severity] += 1

            if event.severity in ("ERROR", "CRITICAL"):
                errors_detected += 1

            batch.append(event)
            if len(batch) >= BATCH_SIZE:
                await self.persist_batch(batch)
                batch = []

        if batch:
            await self.persist_batch(batch)

        elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000.0

        return IngestionResult(
            filename=filename,
            total_parsed=total_parsed,
            errors_detected=errors_detected,
            service_breakdown=dict(service_counts),
            severity_breakdown=dict(severity_counts),
            duration_ms=round(elapsed_ms, 2),
        )

    async def _update_redis_metrics(self, events: list[CanonicalLogEvent]) -> None:
        """Increment rolling Redis counters using pipeline execution."""
        if self.redis is None:
            return

        try:
            pipe = self.redis.pipeline()
            now = datetime.now(UTC)
            # 1-minute bucket timestamp
            bucket_1m = int(now.timestamp() // 60) * 60

            for e in events:
                pipe.incr("tracemind:metrics:logs:total")
                pipe.incr(f"tracemind:metrics:severity:{e.severity}")
                pipe.incr(f"tracemind:metrics:service:{e.service_name}")

                if e.severity in ("ERROR", "CRITICAL"):
                    pipe.incr("tracemind:metrics:errors:total")
                    # Rolling 1-minute bucket with 1-hour expiration
                    bucket_key = f"tracemind:metrics:errors:1m:{bucket_1m}"
                    pipe.incr(bucket_key)
                    pipe.expire(bucket_key, 3600)

                if e.error_signature:
                    pipe.incr(f"tracemind:metrics:signature:{e.error_signature}")

            await pipe.execute()
        except Exception as exc:
            logger.warning(f"Failed to update Redis rolling metrics: {exc}")

    async def search_logs(
        self,
        service_name: str | None = None,
        severity: str | None = None,
        error_signature: str | None = None,
        query: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[CanonicalLogEvent], int]:
        """
        Search indexed log events with multi-criteria filtering and pagination.
        Returns a tuple of (events, total_count).
        """
        base_query = select(LogEventModel)
        count_query = select(func.count()).select_from(LogEventModel)

        filters = []
        if service_name:
            filters.append(LogEventModel.service_name == service_name)
        if severity:
            filters.append(LogEventModel.severity == severity.upper())
        if error_signature:
            filters.append(LogEventModel.error_signature == error_signature)
        if start_time:
            filters.append(LogEventModel.timestamp >= start_time)
        if end_time:
            filters.append(LogEventModel.timestamp <= end_time)
        if query:
            filters.append(LogEventModel.message.ilike(f"%{query}%"))

        if filters:
            base_query = base_query.where(*filters)
            count_query = count_query.where(*filters)

        # Get total count
        count_res = await self.db.execute(count_query)
        total_count = count_res.scalar() or 0

        # Execute paginated query
        base_query = base_query.order_by(desc(LogEventModel.timestamp)).limit(limit).offset(offset)
        result = await self.db.execute(base_query)
        models = result.scalars().all()

        return [m.to_canonical() for m in models], total_count

    async def get_by_event_id(self, event_id: str) -> CanonicalLogEvent | None:
        """Retrieve a specific log event by canonical UUID."""
        stmt = select(LogEventModel).where(LogEventModel.event_id == event_id)
        result = await self.db.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_canonical() if model else None
