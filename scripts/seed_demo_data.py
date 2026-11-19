"""
Turnkey demo dataset seeding script for TraceMind AI.
Populates realistic distributed failure telemetry, creates correlated incidents,
indexes operational runbooks into pgvector, and generates evidence-grounded RCA reports.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.database import async_session_maker
from app.models.incident import IncidentEventCorrelationModel, IncidentModel
from app.models.log_event import LogEventModel
from app.schemas.rag import DocumentCreateRequest
from app.schemas.rca import RCARequest
from app.services.rag_service import RAGService
from app.services.rca_service import RCAService

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("tracemind.seed")


async def seed_demo_data() -> None:
    logger.info("Initializing TraceMind AI demo dataset seeding...")

    async with async_session_maker() as db:
        now = datetime.now(UTC)
        incident_id = "INC-2026-8812"

        # 1. Check or create demo incident
        logger.info("Creating correlated incident '%s'...", incident_id)
        inc = IncidentModel(
            id=str(uuid4()),
            incident_id=incident_id,
            title="Database Connection Pool Starvation in Payment Gateway",
            status="INVESTIGATING",
            severity="CRITICAL",
            lead_service="payment-gateway",
            affected_services=["payment-gateway", "order-api", "notification-service"],
            error_signatures=[
                "pg_conn_timeout:pool_exhausted",
                "http_504_gateway_timeout",
            ],
            started_at=now - timedelta(hours=2),
            detected_at=now - timedelta(hours=1, minutes=48),
            created_at=now - timedelta(hours=1, minutes=48),
            updated_at=now,
        )
        db.add(inc)

        # 2. Seed realistic log telemetry
        logger.info(
            "Seeding log event telemetry across payment-gateway and order-api..."
        )
        events = [
            LogEventModel(
                id=str(uuid4()),
                event_id=f"evt-demo-{i}",
                timestamp=now - timedelta(minutes=60 - i * 2),
                severity="CRITICAL" if i % 2 == 0 else "ERROR",
                service_name="payment-gateway" if i < 15 else "order-api",
                environment="production",
                message=(
                    "sqlalchemy.exc.TimeoutError: QueuePool limit of size 50 reached"
                    if i < 15
                    else "httpx.HTTPStatusError: 504 Gateway Timeout on /v1/charge"
                ),
                exception_type="TimeoutError" if i < 15 else "HTTPStatusError",
                stack_trace='File "/app/db/pool.py", line 88, in acquire\n    raise TimeoutError("Pool exhausted")',
                error_signature="pg_conn_timeout:pool_exhausted"
                if i < 15
                else "http_504_gateway_timeout",
                request_id=f"req-demo-{100 + i}",
                trace_id="trace-demo-99120",
                source_file="db/pool.py" if i < 15 else "clients/payment.py",
                line_number=88 if i < 15 else 115,
                attributes={"active_pool": 50, "max_pool": 50},
                created_at=now,
            )
            for i in range(25)
        ]
        db.add_all(events)
        await db.flush()

        # 3. Associate correlated events with incident
        logger.info("Correlating log events into incident cluster...")
        for ev in events[:10]:
            corr = IncidentEventCorrelationModel(
                id=str(uuid4()),
                incident_id=incident_id,
                log_event_id=ev.event_id,
                correlation_reason="SHARED_TRACE_AND_ERROR_SIGNATURE",
                confidence_score=0.95,
                created_at=now,
            )
            db.add(corr)

        await db.commit()

        # 4. Seed operational runbook into RAG pgvector knowledge base
        logger.info("Indexing operational runbook into RAG pgvector store...")
        runbook_path = (
            Path(__file__).resolve().parent.parent
            / "docs"
            / "runbooks"
            / "sample_db_pool_saturation.md"
        )
        if runbook_path.exists():
            content = runbook_path.read_text(encoding="utf-8")
            rag_service = RAGService(db=db)
            doc_req = DocumentCreateRequest(
                title="PostgreSQL Connection Pool Sizing and Saturation Remediation",
                document_type="runbook",
                source="docs/runbooks/sample_db_pool_saturation.md",
                content=content,
            )
            try:
                doc = await rag_service.create_document(doc_req)
                logger.info(
                    "Indexed runbook doc_id='%s' with %d chunks.",
                    doc.id,
                    doc.chunk_count,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "RAG indexing encountered notice (may already exist or mock mode): %s",
                    e,
                )

        # 5. Synthesize initial Root Cause Analysis (RCA)
        logger.info(
            "Verifying Root Cause Analysis (RCA) engine on '%s'...", incident_id
        )
        rca_service = RCAService(db=db)
        try:
            rca = await rca_service.generate_rca(RCARequest(incident_id=incident_id))
            logger.info(
                "RCA successfully formulated %d hypotheses.", len(rca.hypotheses)
            )
            logger.info("Primary Root Cause: %s", rca.primary_root_cause)
        except Exception as e:  # noqa: BLE001
            logger.warning("RCA synthesis notice: %s", e)

    logger.info("Successfully seeded TraceMind AI demo dataset!")


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
