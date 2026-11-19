"""FastAPI endpoints for log ingestion, querying, and retrieval."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_redis
from app.log_processing.parsers.factory import get_log_parser
from app.log_processing.validator import FileUploadValidator, stream_log_lines
from app.schemas.log_event import CanonicalLogEvent
from app.services.log_service import IngestionResult, LogService

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.post(
    "/upload",
    response_model=IngestionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest an application log file",
    description="Streams and parses multi-format log files, applies PII redaction, computes error signatures, and persists events in micro-batches.",
)
async def upload_log_file(
    file: UploadFile = File(...),
    service_name: str = Query(default="app-service", description="Emitting service name"),
    environment: str = Query(default="production", description="Runtime environment"),
    format_hint: str | None = Query(
        default=None,
        description="Explicit log format ('json', 'python', 'java', 'nginx', 'docker'). Auto-detected if omitted.",
    ),
    db: AsyncSession = Depends(get_db_session),
    redis: Any = Depends(get_redis),
) -> IngestionResult:
    """Validate file, stream lines, parse canonical events, and batch persist."""
    validator = FileUploadValidator()
    sanitized_filename, _ = await validator.validate_upload(file)

    # Sniff format from the first 20 lines if not specified
    sample_lines: list[str] = []
    header_preview = await file.read(4096)
    await file.seek(0)
    sample_lines = header_preview.decode("utf-8", errors="replace").splitlines()[:20]

    parser = get_log_parser(
        format_hint=format_hint,
        sample_lines=sample_lines,
        service_name=service_name,
        environment=environment,
    )

    line_stream = stream_log_lines(file)
    event_stream = parser.parse_async_stream(line_stream, source_file=sanitized_filename)

    service = LogService(db=db, redis_client=redis)
    result = await service.ingest_stream(event_stream=event_stream, filename=sanitized_filename)
    return result


@router.get(
    "",
    response_model=dict[str, Any],
    summary="Query application log events",
    include_in_schema=False,
)
@router.get(
    "/search",
    response_model=dict[str, Any],
    summary="Search indexed log events",
    description="Filter canonical logs across service, severity, error signature, time windows, and text queries.",
)
async def search_logs(
    service_name: Annotated[
        str | None, Query(description="Filter by emitting microservice")
    ] = None,
    severity: Annotated[str | None, Query(description="Filter by normalized log severity")] = None,
    error_signature: Annotated[
        str | None, Query(description="Filter by deterministic SHA-256 error signature")
    ] = None,
    query: Annotated[str | None, Query(description="Full text substring match in message")] = None,
    start_time: Annotated[
        datetime | None, Query(description="Inclusive start timestamp (UTC)")
    ] = None,
    end_time: Annotated[datetime | None, Query(description="Inclusive end timestamp (UTC)")] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Page size limit")] = 50,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Search log records with pagination."""
    service = LogService(db=db)
    events, total = await service.search_logs(
        service_name=service_name,
        severity=severity,
        error_signature=error_signature,
        query=query,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    serialized_events = [e.model_dump() for e in events]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": serialized_events,
        "events": serialized_events,
    }


@router.get(
    "/{event_id}",
    response_model=CanonicalLogEvent,
    summary="Get detailed log event by ID",
)
async def get_log_event(
    event_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CanonicalLogEvent:
    """Retrieve full canonical log event record."""
    service = LogService(db=db)
    event = await service.get_by_event_id(event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log event with event_id '{event_id}' was not found.",
        )
    return event
