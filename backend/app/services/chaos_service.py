"""Service layer orchestrating chaos failure injection and simulated outage telemetry."""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import AnomalyModel
from app.models.incident import IncidentCorrelationModel, IncidentModel
from app.models.log_event import LogEventModel
from app.schemas.chaos import (
    ChaosScenario,
    ChaosSimulateRequest,
    ChaosSimulateResponse,
    ScenarioMetadata,
)
from app.schemas.incident import (
    CorrelationType,
    IncidentResponse,
    IncidentSeverity,
    IncidentStatus,
)
from app.schemas.rag import DocumentCreate, DocumentSourceType
from app.schemas.rca import RCARequest
from app.services.rag_service import RAGService
from app.services.rca_service import RCAService

logger = logging.getLogger("tracemind.services.chaos")


class ChaosService:
    """Coordinates realistic synthetic telemetry generation and incident injection."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def get_available_scenarios(self) -> list[ScenarioMetadata]:
        """Return catalog of available preconfigured chaos failure scenarios."""
        return [
            ScenarioMetadata(
                scenario=ChaosScenario.DB_POOL_STARVATION,
                name="PostgreSQL Connection Pool Starvation",
                description="Exhaustion of SQLAlchemy database pool in payment-gateway causing cascading HTTP 504 timeouts in order-api.",
                lead_service="payment-gateway",
                affected_services=["payment-gateway", "order-api", "checkout-web"],
                severity="CRITICAL",
                symptoms=[
                    "QueuePool limit of size 50 reached",
                    "HTTP 504 Gateway Timeouts on checkout",
                    "Database connection acquisition latency > 30s",
                ],
                icon="database",
            ),
            ScenarioMetadata(
                scenario=ChaosScenario.REDIS_CACHE_FAILOVER,
                name="Redis Cache Eviction & Session Stampede",
                description="Redis cluster master node failover drops cached JWT session tokens, triggering high-volume database query stampedes.",
                lead_service="auth-service",
                affected_services=["auth-service", "api-gateway", "user-web"],
                severity="HIGH",
                symptoms=[
                    "P99 session verification latency surges to 2400ms",
                    "ConnectionRefusedError on redis://auth-cache:6379",
                    "Thundering herd SQL queries on users table",
                ],
                icon="zap",
            ),
            ScenarioMetadata(
                scenario=ChaosScenario.KAFKA_CONSUMER_LAG,
                name="Kafka Consumer Rebalance Storm & Lag Spike",
                description="Unbalanced partition heartbeat timeouts cause recurring rebalances, halting order event ingestion and accumulating massive backlog.",
                lead_service="order-processing-worker",
                affected_services=[
                    "order-processing-worker",
                    "inventory-service",
                    "fulfillment-api",
                ],
                severity="HIGH",
                symptoms=[
                    "CommitFailedError during rebalance in progress",
                    "Consumer lag records surge to 48,000+",
                    "Inventory fulfillment delays exceeding 15 minutes",
                ],
                icon="layers",
            ),
            ScenarioMetadata(
                scenario=ChaosScenario.POD_MEMORY_LEAK,
                name="JVM Heap Exhaustion & Pod OOMKilled",
                description="Progressive uncollected document buffer memory leak triggers intensive garbage collection pauses and container exit code 137.",
                lead_service="search-indexer",
                affected_services=["search-indexer", "catalog-api"],
                severity="CRITICAL",
                symptoms=[
                    "Container terminated with Exit Code 137 (OOMKilled)",
                    "java.lang.OutOfMemoryError: Java heap space",
                    "Catalog search queries failing with HTTP 503",
                ],
                icon="cpu",
            ),
        ]

    async def simulate_incident(self, request: ChaosSimulateRequest) -> ChaosSimulateResponse:
        """
        Inject synthetic failure telemetry (logs, anomalies, runbooks) and correlate
        an operational incident cluster ready for instant AI investigation.
        """
        scenario = request.scenario
        now = datetime.now(UTC)
        rnd_suffix = random.randint(1000, 9999)
        incident_id = f"INC-2026-{rnd_suffix}"
        trace_id = f"trace-chaos-{rnd_suffix}"

        logger.info(
            "Simulating chaos failure scenario '%s' (Incident %s)...",
            scenario,
            incident_id,
        )

        # 1. Determine scenario parameters
        if scenario == ChaosScenario.REDIS_CACHE_FAILOVER:
            title = (
                request.custom_title or "Redis Cluster Failover & Cache Stampede in Auth Service"
            )
            description = (
                "Cluster master node failover triggered connection reset. Cache misses caused an immediate "
                "thundering herd on the primary Postgres user credentials database."
            )
            lead_service = "auth-service"
            affected_services = ["auth-service", "api-gateway", "user-web"]
            severity_str = "HIGH"
            error_signatures = [
                "redis_timeout:cluster_failover",
                "auth_session_expired:thundering_herd",
            ]
            events_data = self._generate_redis_events(now, trace_id, rnd_suffix)
            anomalies_data = [
                {
                    "metric_name": "p99_latency_ms",
                    "current_value": 2480.0,
                    "baseline_mean": 45.0,
                    "baseline_std": 12.0,
                    "threshold": 150.0,
                    "anomaly_score": 0.94,
                    "severity": "HIGH",
                    "detection_method": "IQR",
                }
            ]
            runbook_title = "Redis Cluster Latency Spike and Cache Stampede Mitigation"
            runbook_content = (
                "# RUNBOOK-CACHE-02: Redis Cluster Failover & Stampede Remediation\n\n"
                "## Immediate Actions:\n"
                "1. Verify Sentinel / Redis Cluster quorum: `redis-cli -p 6379 cluster nodes`\n"
                "2. Enable token caching fallback with probabilistic early expiration (XFetch algorithm).\n"
                "3. Throttle downstream auth traffic at the Envoy API Gateway layer."
            )

        elif scenario == ChaosScenario.KAFKA_CONSUMER_LAG:
            title = (
                request.custom_title or "Kafka Consumer Group Rebalance Storm & Event Pipeline Lag"
            )
            description = (
                "Heartbeat timeout in order-processing-worker triggered partition rebalancing loops. "
                "Consumers unable to commit offsets, leading to an accumulated consumer lag of 48,000 messages."
            )
            lead_service = "order-processing-worker"
            affected_services = [
                "order-processing-worker",
                "inventory-service",
                "fulfillment-api",
            ]
            severity_str = "HIGH"
            error_signatures = [
                "kafka_commit_failed:rebalance_in_progress",
                "consumer_lag_threshold_exceeded",
            ]
            events_data = self._generate_kafka_events(now, trace_id, rnd_suffix)
            anomalies_data = [
                {
                    "metric_name": "consumer_lag_records",
                    "current_value": 48250.0,
                    "baseline_mean": 120.0,
                    "baseline_std": 35.0,
                    "threshold": 1000.0,
                    "anomaly_score": 0.91,
                    "severity": "HIGH",
                    "detection_method": "Z_SCORE",
                }
            ]
            runbook_title = "Kafka Consumer Lag and Rebalance Storm Runbook"
            runbook_content = (
                "# RUNBOOK-MQ-05: Kafka Consumer Lag and Rebalance Remediation\n\n"
                "## Immediate Actions:\n"
                "1. Inspect active consumer group state: `kafka-consumer-groups.sh --bootstrap-server kafka:9092 --describe --group order-processors`\n"
                "2. Increase max.poll.interval.ms to 600000 to prevent premature coordinator expulsion.\n"
                "3. Scale consumer deployment replicas from 4 to 8."
            )

        elif scenario == ChaosScenario.POD_MEMORY_LEAK:
            title = request.custom_title or "JVM Heap Exhaustion & Pod OOMKilled in Search Indexer"
            description = (
                "Progressive buffer leak in search-indexer caused persistent high tenured generation usage, "
                "culminating in an unhandled OutOfMemoryError and kernel OOMKiller SIGKILL (exit code 137)."
            )
            lead_service = "search-indexer"
            affected_services = ["search-indexer", "catalog-api"]
            severity_str = "CRITICAL"
            error_signatures = [
                "oom_killer:exit_code_137",
                "heap_allocation_failure",
            ]
            events_data = self._generate_oom_events(now, trace_id, rnd_suffix)
            anomalies_data = [
                {
                    "metric_name": "memory_utilization_pct",
                    "current_value": 99.4,
                    "baseline_mean": 62.0,
                    "baseline_std": 4.5,
                    "threshold": 85.0,
                    "anomaly_score": 0.98,
                    "severity": "CRITICAL",
                    "detection_method": "ISOLATION_FOREST",
                }
            ]
            runbook_title = "JVM Memory Leaks and Kubernetes OOMKill Mitigation"
            runbook_content = (
                "# RUNBOOK-JVM-01: JVM Heap Exhaustion & Pod OOMKill Mitigation\n\n"
                "## Immediate Actions:\n"
                "1. Inspect pod restart history: `kubectl describe pod -l app=search-indexer -n production`\n"
                "2. Trigger automated heap dump: `jcmd 1 GC.heap_dump /tmp/heap.hprof`\n"
                "3. Temporarily increase container memory limit to 4Gi in deployment spec."
            )

        else:
            # Default: DB_POOL_STARVATION
            title = (
                request.custom_title or "PostgreSQL Connection Pool Starvation in Payment Gateway"
            )
            description = (
                "Elevated acquisition latency and unreleased database transactions exhausted the "
                "SQLAlchemy connection pool in payment-gateway, propagating cascading 504 timeouts to order-api."
            )
            lead_service = "payment-gateway"
            affected_services = ["payment-gateway", "order-api", "checkout-web"]
            severity_str = "CRITICAL"
            error_signatures = [
                "pg_conn_timeout:pool_exhausted",
                "http_504_gateway_timeout",
            ]
            events_data = self._generate_db_events(now, trace_id, rnd_suffix)
            anomalies_data = [
                {
                    "metric_name": "error_rate",
                    "current_value": 58.4,
                    "baseline_mean": 2.5,
                    "baseline_std": 0.8,
                    "threshold": 10.0,
                    "anomaly_score": 0.96,
                    "severity": "CRITICAL",
                    "detection_method": "Z_SCORE",
                }
            ]
            runbook_title = "PostgreSQL Connection Pool Sizing and Saturation Remediation"
            runbook_content = (
                "# RUNBOOK-DB-04: PostgreSQL Connection Pool Sizing and Saturation Remediation\n\n"
                "## Immediate Actions:\n"
                "1. Inspect active connection states: `SELECT count(*), state FROM pg_stat_activity GROUP BY 2;`\n"
                "2. Check for long-running blocking transactions holding exclusive locks.\n"
                "3. Increase PgBouncer max client connections and expand application pool limit."
            )

        # 2. Persist Incident
        incident_pk = str(uuid4())
        inc_model = IncidentModel(
            id=incident_pk,
            incident_id=incident_id,
            title=title,
            description=description,
            status="INVESTIGATING",
            severity=severity_str,
            lead_service=lead_service,
            affected_services=affected_services,
            error_signatures=error_signatures,
            started_at=now - timedelta(minutes=45),
            detected_at=now - timedelta(minutes=38),
            metadata_={
                "chaos_injected": True,
                "scenario": scenario.value,
                "simulated_at": now.isoformat(),
            },
            created_at=now,
            updated_at=now,
        )
        self.db.add(inc_model)
        await self.db.flush()

        # 3. Persist Log Events
        created_log_models: list[LogEventModel] = []
        for ev in events_data:
            log_m = LogEventModel(
                id=str(uuid4()),
                event_id=ev["event_id"],
                timestamp=ev["timestamp"],
                severity=ev["severity"],
                service_name=ev["service_name"],
                environment="production",
                message=ev["message"],
                exception_type=ev.get("exception_type"),
                stack_trace=ev.get("stack_trace"),
                error_signature=ev.get("error_signature"),
                request_id=ev.get("request_id"),
                trace_id=trace_id,
                source_file=ev.get("source_file"),
                line_number=ev.get("line_number"),
                attributes={"chaos_scenario": scenario.value},
                created_at=now,
            )
            created_log_models.append(log_m)
            self.db.add(log_m)

        await self.db.flush()

        # 4. Associate Incident Correlations
        for idx, lm in enumerate(created_log_models[:8]):
            corr = IncidentCorrelationModel(
                id=str(uuid4()),
                incident_id=inc_model.id,
                event_id=lm.event_id,
                correlation_type=CorrelationType.CONFIRMED_CAUSAL.value
                if idx < 4
                else CorrelationType.CASCADING_FAILURE.value,
                confidence_score=0.96 - (idx * 0.02),
                reason=f"Correlated via trace_id '{trace_id}' and cascading error signatures",
                created_at=now,
            )
            self.db.add(corr)

        # 5. Persist Statistical Anomalies
        for an in anomalies_data:
            anom_id = f"anom-chaos-{rnd_suffix}-{an['metric_name']}"
            anom_m = AnomalyModel(
                id=str(uuid4()),
                anomaly_id=anom_id,
                service_name=lead_service,
                timestamp=now - timedelta(minutes=38),
                metric_name=an["metric_name"],
                current_value=an["current_value"],
                baseline_mean=an.get("baseline_mean"),
                baseline_std=an.get("baseline_std"),
                threshold=an["threshold"],
                anomaly_score=an["anomaly_score"],
                severity=an["severity"],
                detection_method=an["detection_method"],
                details={"chaos_scenario": scenario.value, "trace_id": trace_id},
                incident_id=inc_model.id,
                created_at=now,
            )
            self.db.add(anom_m)

        # 6. Index Runbook into pgvector RAG (idempotent)
        rag_service = RAGService(db=self.db)
        doc_req = DocumentCreate(
            title=runbook_title,
            source_type=DocumentSourceType.RUNBOOK,
            service_name=lead_service,
            category="chaos_simulation",
            content=runbook_content,
            metadata={"scenario": scenario.value, "source": "chaos_injection"},
        )
        try:
            await rag_service.create_document(doc_req)
        except Exception as e:  # noqa: BLE001
            logger.debug("Runbook indexing notice during chaos injection: %s", e)

        # Commit all telemetry
        await self.db.commit()

        # 7. Synthesize initial Root Cause Analysis (RCA)
        rca_service = RCAService(db=self.db)
        try:
            await rca_service.generate_rca(RCARequest(incident_id=incident_id))
        except Exception as e:  # noqa: BLE001
            logger.warning("RCA generation notice during chaos simulation: %s", e)

        inc_resp = IncidentResponse(
            id=inc_model.id,
            incident_id=inc_model.incident_id,
            title=inc_model.title,
            description=inc_model.description,
            status=IncidentStatus(inc_model.status),
            severity=IncidentSeverity(inc_model.severity),
            lead_service=inc_model.lead_service,
            affected_services=inc_model.affected_services,
            error_signatures=inc_model.error_signatures,
            started_at=inc_model.started_at,
            detected_at=inc_model.detected_at,
            correlated_event_count=len(created_log_models),
            metadata=inc_model.metadata_,
            created_at=inc_model.created_at,
            updated_at=inc_model.updated_at,
        )

        return ChaosSimulateResponse(
            incident=inc_resp,
            scenario=scenario,
            injected_logs_count=len(created_log_models),
            injected_anomalies_count=len(anomalies_data),
            runbook_title=runbook_title,
            message=f"Chaos scenario '{scenario.value}' injected successfully. Incident {incident_id} created with correlated telemetry.",
            extra_details={
                "incident_id": incident_id,
                "lead_service": lead_service,
                "trace_id": trace_id,
            },
        )

    # ------------------------------------------------------------------
    # Synthetic Telemetry Generators
    # ------------------------------------------------------------------

    def _generate_db_events(
        self, now: datetime, trace_id: str, suffix: int
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for i in range(16):
            is_payment = i < 10
            events.append(
                {
                    "event_id": f"evt-chaos-db-{suffix}-{i}",
                    "timestamp": now - timedelta(minutes=40 - i * 2),
                    "severity": "CRITICAL" if i % 2 == 0 else "ERROR",
                    "service_name": "payment-gateway" if is_payment else "order-api",
                    "message": (
                        "sqlalchemy.exc.TimeoutError: QueuePool limit of size 50 overflow 10 reached, connection timed out"
                        if is_payment
                        else "httpx.HTTPStatusError: 504 Gateway Timeout on /v1/charge - downstream payment-gateway timed out"
                    ),
                    "exception_type": "TimeoutError" if is_payment else "HTTPStatusError",
                    "stack_trace": (
                        'File "/app/db/pool.py", line 88, in acquire\n    raise TimeoutError("QueuePool limit reached")'
                        if is_payment
                        else 'File "/app/clients/payment.py", line 115, in charge\n    raise HTTPStatusError("504 Gateway Timeout")'
                    ),
                    "error_signature": (
                        "pg_conn_timeout:pool_exhausted"
                        if is_payment
                        else "http_504_gateway_timeout"
                    ),
                    "request_id": f"req-chaos-{suffix}-{i}",
                    "source_file": "db/pool.py" if is_payment else "clients/payment.py",
                    "line_number": 88 if is_payment else 115,
                }
            )
        return events

    def _generate_redis_events(
        self, now: datetime, trace_id: str, suffix: int
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for i in range(16):
            is_auth = i < 10
            events.append(
                {
                    "event_id": f"evt-chaos-redis-{suffix}-{i}",
                    "timestamp": now - timedelta(minutes=35 - i * 2),
                    "severity": "CRITICAL" if i % 2 == 0 else "ERROR",
                    "service_name": "auth-service" if is_auth else "api-gateway",
                    "message": (
                        "aioredis.exceptions.ConnectionError: Error connecting to redis://auth-cache:6379: ConnectionRefusedError"
                        if is_auth
                        else "httpx.HTTPStatusError: 401 Unauthorized - Token cache miss caused downstream auth worker timeout"
                    ),
                    "exception_type": "ConnectionError" if is_auth else "HTTPStatusError",
                    "stack_trace": (
                        'File "/app/cache/redis.py", line 142, in get_session\n    raise ConnectionError("Cluster failover in progress")'
                        if is_auth
                        else 'File "/app/middleware/auth.py", line 64, in authenticate\n    raise HTTPStatusError("401 Unauthorized")'
                    ),
                    "error_signature": (
                        "redis_timeout:cluster_failover"
                        if is_auth
                        else "auth_session_expired:thundering_herd"
                    ),
                    "request_id": f"req-chaos-redis-{suffix}-{i}",
                    "source_file": "cache/redis.py" if is_auth else "middleware/auth.py",
                    "line_number": 142 if is_auth else 64,
                }
            )
        return events

    def _generate_kafka_events(
        self, now: datetime, trace_id: str, suffix: int
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for i in range(16):
            is_worker = i < 11
            events.append(
                {
                    "event_id": f"evt-chaos-kafka-{suffix}-{i}",
                    "timestamp": now - timedelta(minutes=30 - i * 2),
                    "severity": "CRITICAL" if i % 2 == 0 else "ERROR",
                    "service_name": (
                        "order-processing-worker" if is_worker else "inventory-service"
                    ),
                    "message": (
                        "kafka.errors.CommitFailedError: Commit cannot be completed since the group has already rebalanced"
                        if is_worker
                        else "inventory.exceptions.StockAllocationTimeout: Stock lock blocked waiting for order-worker queue clearance"
                    ),
                    "exception_type": (
                        "CommitFailedError" if is_worker else "StockAllocationTimeout"
                    ),
                    "stack_trace": (
                        'File "/app/consumers/order_consumer.py", line 203, in commit\n    raise CommitFailedError("Rebalance in progress")'
                        if is_worker
                        else 'File "/app/services/inventory.py", line 87, in allocate\n    raise StockAllocationTimeout("Queue stall")'
                    ),
                    "error_signature": (
                        "kafka_commit_failed:rebalance_in_progress"
                        if is_worker
                        else "consumer_lag_threshold_exceeded"
                    ),
                    "request_id": f"req-chaos-kafka-{suffix}-{i}",
                    "source_file": (
                        "consumers/order_consumer.py" if is_worker else "services/inventory.py"
                    ),
                    "line_number": 203 if is_worker else 87,
                }
            )
        return events

    def _generate_oom_events(
        self, now: datetime, trace_id: str, suffix: int
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for i in range(16):
            is_indexer = i < 10
            events.append(
                {
                    "event_id": f"evt-chaos-oom-{suffix}-{i}",
                    "timestamp": now - timedelta(minutes=32 - i * 2),
                    "severity": "CRITICAL" if i % 2 == 0 else "ERROR",
                    "service_name": "search-indexer" if is_indexer else "catalog-api",
                    "message": (
                        "java.lang.OutOfMemoryError: Java heap space - continuous GC allocation failure (exit code 137)"
                        if is_indexer
                        else "catalog.exceptions.SearchBackendUnavailable: Search indexer unreachable on port 9200 (HTTP 503)"
                    ),
                    "exception_type": (
                        "OutOfMemoryError" if is_indexer else "SearchBackendUnavailable"
                    ),
                    "stack_trace": (
                        'File "SearchIndexer.java", line 312, in processBatch\n    throw new OutOfMemoryError("Heap limit exceeded");'
                        if is_indexer
                        else 'File "/app/clients/search.py", line 78, in search\n    raise SearchBackendUnavailable("Backend OOMKilled")'
                    ),
                    "error_signature": (
                        "oom_killer:exit_code_137" if is_indexer else "heap_allocation_failure"
                    ),
                    "request_id": f"req-chaos-oom-{suffix}-{i}",
                    "source_file": ("SearchIndexer.java" if is_indexer else "clients/search.py"),
                    "line_number": 312 if is_indexer else 78,
                }
            )
        return events
