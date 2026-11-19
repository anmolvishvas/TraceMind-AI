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

# Ensure backend directory or /app is in sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if backend_path.exists():
    sys.path.insert(0, str(backend_path))
app_path = Path("/app")
if app_path.exists() and str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from sqlalchemy import delete, select  # noqa: E402

from app.core.database import async_session_maker  # noqa: E402
from app.models.incident import IncidentCorrelationModel, IncidentModel  # noqa: E402
from app.models.log_event import LogEventModel  # noqa: E402
from app.schemas.incident import CorrelationType  # noqa: E402
from app.schemas.rag import DocumentCreate, DocumentSourceType  # noqa: E402
from app.schemas.rca import RCARequest  # noqa: E402
from app.services.rag_service import RAGService  # noqa: E402
from app.services.rca_service import RCAService  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("tracemind.seed")


async def seed_demo_data() -> None:
    logger.info("Initializing TraceMind AI demo dataset seeding...")

    async with async_session_maker() as db:
        now = datetime.now(UTC)
        incident_id = "INC-2026-8812"

        # 1. Clean previous demo logs to guarantee idempotency
        logger.info("Cleaning any previous demo telemetry for clean idempotency...")
        await db.execute(
            delete(LogEventModel).where(LogEventModel.event_id.startswith("evt-demo-"))
        )

        # 2. Check or create demo incident
        stmt = select(IncidentModel).where(IncidentModel.incident_id == incident_id)
        res = await db.execute(stmt)
        inc = res.scalar_one_or_none()

        if inc is None:
            logger.info("Creating correlated incident '%s'...", incident_id)
            inc = IncidentModel(
                id=str(uuid4()),
                incident_id=incident_id,
                title="Database Connection Pool Starvation in Payment Gateway",
                description="Elevated connection timeout errors causing cascading 504 Gateway Timeouts across order processing checkout pipeline.",
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
                metadata_={
                    "customer_impact": "High",
                    "sla_breached": False,
                    "region": "us-east-1",
                },
                created_at=now - timedelta(hours=1, minutes=48),
                updated_at=now,
            )
            db.add(inc)
            await db.flush()
        else:
            logger.info("Reusing existing demo incident '%s' (UUID=%s)...", incident_id, inc.id)
            await db.execute(
                delete(IncidentCorrelationModel).where(
                    IncidentCorrelationModel.incident_id == inc.id
                )
            )
            inc.updated_at = now
            await db.flush()

        # 3. Seed realistic log telemetry
        logger.info("Seeding log event telemetry across payment-gateway and order-api...")
        events = [
            LogEventModel(
                id=str(uuid4()),
                event_id=f"evt-demo-{i}",
                timestamp=now - timedelta(minutes=60 - i * 2),
                severity="CRITICAL" if i % 2 == 0 else "ERROR",
                service_name="payment-gateway" if i < 15 else "order-api",
                environment="production",
                message=(
                    "sqlalchemy.exc.TimeoutError: QueuePool limit of size 50 overflow 10 reached, connection timed out, timeout 30.00"
                    if i < 15
                    else "httpx.HTTPStatusError: 504 Gateway Timeout on /v1/charge - downstream payment-gateway timed out"
                ),
                exception_type="TimeoutError" if i < 15 else "HTTPStatusError",
                stack_trace=(
                    'File "/app/db/pool.py", line 88, in acquire\n    raise TimeoutError("QueuePool limit reached")'
                    if i < 15
                    else 'File "/app/clients/payment.py", line 115, in charge\n    raise HTTPStatusError("504 Gateway Timeout")'
                ),
                error_signature="pg_conn_timeout:pool_exhausted"
                if i < 15
                else "http_504_gateway_timeout",
                request_id=f"req-demo-{100 + i}",
                trace_id="trace-demo-99120",
                source_file="db/pool.py" if i < 15 else "clients/payment.py",
                line_number=88 if i < 15 else 115,
                attributes={"active_pool": 50, "max_pool": 50, "overflow": 10},
                created_at=now,
            )
            for i in range(25)
        ]
        db.add_all(events)
        await db.flush()

        # 4. Associate correlated events with incident
        logger.info("Correlating log events into incident cluster...")
        for ev in events[:10]:
            corr = IncidentCorrelationModel(
                id=str(uuid4()),
                incident_id=inc.id,
                event_id=ev.event_id,
                correlation_type=CorrelationType.CONFIRMED_CAUSAL.value,
                confidence_score=0.95,
                reason="Shared trace_id and error signature cascade",
                created_at=now,
            )
            db.add(corr)

        await db.commit()

        # 5. Seed operational runbook into RAG pgvector knowledge base
        logger.info("Indexing operational runbook into RAG pgvector store...")
        runbook_candidates = [
            Path(__file__).resolve().parent.parent
            / "docs"
            / "runbooks"
            / "sample_db_pool_saturation.md",
            Path("/app/docs/runbooks/sample_db_pool_saturation.md"),
            Path("docs/runbooks/sample_db_pool_saturation.md"),
        ]
        runbook_path = next((p for p in runbook_candidates if p.exists()), None)

        fallback_content = """# RUNBOOK-DB-04: PostgreSQL Connection Pool Sizing and Saturation Remediation
## 1. Trigger Symptoms & Error Signatures
- Application Error: `sqlalchemy.exc.TimeoutError: QueuePool limit of size 50 overflow 10 reached`
- Error Signature: `pg_conn_timeout:pool_exhausted`
- Upstream HTTP 504 Gateway Timeouts on payment-gateway and order-api.

## 2. Immediate Triage & Diagnostic Steps
1. Inspect active connections: `SELECT count(*), state FROM pg_stat_activity GROUP BY 2;`
2. Check for long-running blocking queries in pg_stat_activity.
3. Terminate stalled worker transactions using pg_terminate_backend(pid).

## 3. Remediation & Prevention
- Increase PgBouncer max client connections.
- Ensure all repository database sessions are closed in finally blocks.
"""
        content = runbook_path.read_text(encoding="utf-8") if runbook_path else fallback_content

        rag_service = RAGService(db=db)
        doc_req = DocumentCreate(
            title="PostgreSQL Connection Pool Sizing and Saturation Remediation",
            source_type=DocumentSourceType.RUNBOOK,
            service_name="payment-gateway",
            category="database",
            content=content,
            metadata={"source_file": "docs/runbooks/sample_db_pool_saturation.md"},
        )
        try:
            doc = await rag_service.create_document(doc_req)
            logger.info(
                "Indexed runbook document_id='%s' with %d chunks.",
                doc.document_id,
                doc.total_chunks,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "RAG indexing notice (may already exist or mock mode active): %s",
                e,
            )

        # 6. Synthesize initial Root Cause Analysis (RCA)
        logger.info(
            "Verifying Root Cause Analysis (RCA) engine on '%s'...", incident_id
        )
        rca_service = RCAService(db=db)
        try:
            rca = await rca_service.generate_rca(RCARequest(incident_id=incident_id))
            logger.info(
                "RCA successfully formulated %d hypotheses.", len(rca.hypotheses)
            )
            primary_title = rca.primary_root_cause.title if rca.primary_root_cause else "None"
            logger.info("Primary Root Cause: %s", primary_title)
        except Exception as e:  # noqa: BLE001
            logger.warning("RCA synthesis notice: %s", e)

    logger.info("Successfully seeded TraceMind AI demo dataset!")


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
