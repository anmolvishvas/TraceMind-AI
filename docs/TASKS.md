# TraceMind AI — Phased Implementation Plan

| **Metadata** | **Specification** |
| :--- | :--- |
| **Document Version** | 1.0.0-PROD |
| **System** | **TraceMind AI Incident Intelligence Platform** |
| **Author** | Anmol Vishvas ([anmol23vishvas@gmail.com](mailto:anmol23vishvas@gmail.com)) |
| **Target Repository** | [https://github.com/anmolvishvas/TraceMind-AI](https://github.com/anmolvishvas/TraceMind-AI) |
| **Execution Model** | Incremental, Test-Driven Development (TDD), 7 Phased Milestones |
| **Last Updated** | November 2026 |

---

## Roadmap Overview

```mermaid
flowchart LR
    P1["Phase 1: Foundation & Scaffolding"] --> P2["Phase 2: Ingestion & Log Normalization"]
    P2 --> P3["Phase 3: Statistical Anomaly & Correlation"]
    P3 --> P4["Phase 4: pgvector RAG & LLM RCA"]
    P4 --> P5["Phase 5: Official MCP Python Server"]
    P5 --> P6["Phase 6: React Dashboard & UI"]
    P6 --> P7["Phase 7: Production Readiness & Hardening"]
```

---

## Phase 1: Foundation and Project Scaffolding

- **Objective:** Establish the core repository layout, Python 3.12+ backend workspace, database connection with `pgvector`, Redis client, Docker Compose environment, linting/typing gates, and automated test runners.
- **Estimated Duration:** Sprint 1

### Tasks:
- [x] **TASK-1.1: Core Repository Layout & Packaging Setup**
  - **Description:** Initialize backend and frontend workspace directories using standard Python packaging conventions. Configure `pyproject.toml` with Ruff, mypy (strict), and pytest configurations.
  - **Dependencies:** None.
  - **Files/Modules:** `pyproject.toml`, `.gitignore`, `backend/app/__init__.py`.
  - **Acceptance Criteria:** `ruff check .`, `mypy backend`, and `pytest` execute successfully via CLI.
  - **Tests:** `backend/tests/unit/test_foundation.py`.
  - **Deliverable:** Working Python packaging and tooling foundation.

- [x] **TASK-1.2: Environment Configuration & Pydantic Settings**
  - **Description:** Implement `app/core/config.py` using Pydantic v2 `BaseSettings` to load database URLs, Redis hosts, OpenAI API keys, token limits, and security secrets from environment variables.
  - **Dependencies:** TASK-1.1.
  - **Files/Modules:** `backend/app/core/config.py`.
  - **Acceptance Criteria:** Settings parse valid environment variables; invalid types raise descriptive validation errors.
  - **Tests:** `backend/tests/unit/test_foundation.py`.
  - **Deliverable:** Strongly typed configuration module.

- [x] **TASK-1.3: Asynchronous Database & pgvector Integration**
  - **Description:** Configure SQLAlchemy 2.0 async engine and sessionmaker using `asyncpg`. Enable PostgreSQL `vector` extension and configure Alembic for database migrations.
  - **Dependencies:** TASK-1.2.
  - **Files/Modules:** `backend/app/core/database.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_enable_pgvector_extension.py`.
  - **Acceptance Criteria:** Database connection pool initializes; Alembic applies `vector` extension migration without error.
  - **Tests:** `backend/tests/integration/test_database.py`.
  - **Deliverable:** Operational async database connection layer.

- [x] **TASK-1.4: Redis Connection & Cache Client**
  - **Description:** Set up asynchronous Redis connection pool with connection health checks, retry policies, and helper methods for key expiration and sliding window counters.
  - **Dependencies:** TASK-1.2.
  - **Files/Modules:** `backend/app/core/redis.py`.
  - **Acceptance Criteria:** Redis ping succeeds asynchronously; connection failures trigger retries with exponential backoff.
  - **Tests:** `backend/tests/integration/test_redis.py`.
  - **Deliverable:** High-performance async Redis client.

- [x] **TASK-1.5: FastAPI Application Factory & Health Endpoints**
  - **Description:** Construct the FastAPI application factory (`create_app`) with global exception handlers, CORS middleware, OpenTelemetry request instrumentation, and `/healthz` & `/api/v1/health/readyz` endpoints.
  - **Dependencies:** TASK-1.3, TASK-1.4.
  - **Files/Modules:** `backend/app/main.py`, `backend/app/api/v1/endpoints/health.py`, `backend/app/api/v1/router.py`.
  - **Acceptance Criteria:** `GET /healthz` and `GET /api/v1/health/readyz` return expected payloads with database and Redis operational status.
  - **Tests:** `backend/tests/unit/test_foundation.py`.
  - **Deliverable:** Core web service responding to health checks.

- [x] **TASK-1.6: Docker Compose Multi-Container Orchestration**
  - **Description:** Author production-ready `docker-compose.yml` orchestrating PostgreSQL 16 with `pgvector`, Redis 7.2-alpine, the FastAPI backend, and frontend containers with volume persistence and health checks.
  - **Dependencies:** TASK-1.5.
  - **Files/Modules:** `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`.
  - **Acceptance Criteria:** Running `docker compose up --build` brings up all services into a healthy state without manual intervention.
  - **Tests:** Automated Docker compose verification script.
  - **Deliverable:** Reproducible local and CI development environment.

---

## Phase 2: Log Ingestion and Processing

- **Objective:** Build a high-throughput, streaming log ingestion pipeline supporting multi-format parsing, multi-line stack trace stitching, deterministic error signature hashing, PII scrubbing, and bulk persistence.
- **Estimated Duration:** Sprint 2

### Tasks:
- [x] **TASK-2.1: Canonical Log Event Schema & Validation**
  - **Description:** Define the canonical Pydantic v2 `CanonicalLogEvent` and SQLAlchemy database models, including UUIDv7 event IDs, UTC timestamps, severity enums, and structured metadata.
  - **Dependencies:** TASK-1.3.
  - **Files/Modules:** `backend/app/schemas/log_event.py`, `backend/app/models/log_event.py`.
  - **Acceptance Criteria:** Valid events serialize cleanly; invalid timestamps or unrecognized severities fail validation.
  - **Tests:** `backend/tests/unit/test_log_schemas.py`.
  - **Deliverable:** Canonical log event schema contract.

- [x] **TASK-2.2: File Upload Validation & Streaming Reader**
  - **Description:** Implement multipart file upload endpoint (`POST /api/v1/logs/upload`) with strict MIME validation, magic byte checks, $100\text{ MB}$ size ceiling, and chunked streaming iterators ($O(1)$ memory).
  - **Dependencies:** TASK-2.1.
  - **Files/Modules:** `backend/app/log_processing/validator.py`, `backend/app/api/v1/endpoints/logs.py`.
  - **Acceptance Criteria:** Non-log file types (e.g., `.exe`, `.mp4`) are rejected with `415 Unsupported Media Type`; large uploads stream without memory spikes.
  - **Tests:** `backend/tests/integration/test_upload_validation.py`.
  - **Deliverable:** Hardened file ingestion endpoint.

- [x] **TASK-2.3: Multi-Format Parser Engine**
  - **Description:** Develop dedicated parsers for JSON logs (Bunyan/Zap), Python standard logging, Java Log4j/Logback stack traces, Nginx access logs, and Docker container output.
  - **Dependencies:** TASK-2.1.
  - **Files/Modules:** `backend/app/log_processing/parsers/*.py`.
  - **Acceptance Criteria:** Multi-line Java/Python stack traces are parsed into a single `LogEvent`; malformed lines do not halt ingestion.
  - **Tests:** `backend/tests/unit/test_parsers.py` (with fixtures for all formats).
  - **Deliverable:** Pluggable parsing strategy suite.

- [x] **TASK-2.4: Deterministic Error Signature Fingerprinter**
  - **Description:** Build normalizer to strip memory addresses (`0x...`), line numbers, and timestamps from stack traces and generate SHA-256 `error_signature` hashes.
  - **Dependencies:** TASK-2.3.
  - **Files/Modules:** `backend/app/log_processing/fingerprinter.py`.
  - **Acceptance Criteria:** Identical exceptions with differing memory pointers produce identical SHA-256 signatures.
  - **Tests:** `backend/tests/unit/test_fingerprinter.py`.
  - **Deliverable:** Error signature generation module.

- [x] **TASK-2.5: PII Scrubber & Secret Sanitizer**
  - **Description:** Implement regex sanitizers to mask credit card numbers, JWT tokens, AWS access keys, and passwords prior to storage.
  - **Dependencies:** TASK-2.1.
  - **Files/Modules:** `backend/app/core/security.py`.
  - **Acceptance Criteria:** Sensitive credentials in log messages are replaced with `[REDACTED_SECRET]`.
  - **Tests:** `backend/tests/unit/test_pii_scrubber.py`.
  - **Deliverable:** Enterprise data privacy sanitizer.

- [x] **TASK-2.6: Micro-Batch Log Persistence & Redis Rolling Counters**
  - **Description:** Stream canonical events into bounded micro-batches (500 records) for multi-row insertion into PostgreSQL while updating Redis rolling counters (1m, 5m, 15m).
  - **Dependencies:** TASK-2.3, TASK-2.4.
  - **Files/Modules:** `backend/app/services/log_service.py`.
  - **Acceptance Criteria:** Ingestion sustains $\ge 5,000\text{ events/sec}$ throughput; Redis counters increment atomically.
  - **Tests:** `backend/tests/integration/test_batch_persistence.py`.
  - **Deliverable:** High-throughput persistence service.

---

## Phase 3: Anomaly Detection and Incident Correlation

- **Objective:** Implement statistical anomaly detection (Z-score, IQR, Isolation Forest) completely decoupled from LLMs, and build the multi-dimensional incident correlation engine.
- **Estimated Duration:** Sprint 3

### Tasks:
- [x] **TASK-3.1: Historical Statistical Baseline Calculator**
  - **Description:** Compute 7-day rolling exponential moving averages (EMA) and standard deviations of error rates per service using Redis rolling counters.
  - **Dependencies:** TASK-2.6.
  - **Files/Modules:** `backend/app/anomaly_detection/baseline.py`.
  - **Acceptance Criteria:** Accurate mean and variance calculations across diverse service traffic patterns.
  - **Tests:** `backend/tests/unit/test_baseline.py`.
  - **Deliverable:** Baseline calculation engine.

- [x] **TASK-3.2: Statistical Anomaly Detection Algorithms**
  - **Description:** Implement Z-Score ($> 3\sigma$), Interquartile Range (IQR $> Q_3 + 1.5\text{IQR}$), and Scikit-learn Isolation Forest detectors for multi-metric anomalies.
  - **Dependencies:** TASK-3.1.
  - **Files/Modules:** `backend/app/anomaly_detection/statistical.py`.
  - **Acceptance Criteria:** Injected artificial spikes trigger anomalies with calculated confidence scores; zero calls made to LLMs.
  - **Tests:** `backend/tests/unit/test_anomaly_detection.py`.
  - **Deliverable:** Pure Python statistical detection engine.

- [x] **TASK-3.3: Multi-Dimensional Incident Correlation Engine**
  - **Description:** Cluster anomalous events into unified `Incident` records using temporal proximity ($\pm 5\text{ mins}$), distributed trace IDs, service topology, and error signatures.
  - **Dependencies:** TASK-3.2.
  - **Files/Modules:** `backend/app/incidents/correlator.py`.
  - **Acceptance Criteria:** Cascading microservice failures sharing a trace ID are grouped into 1 incident with `CONFIRMED_CAUSAL` linkage.
  - **Tests:** `backend/tests/unit/test_correlation.py`.
  - **Deliverable:** Deterministic event clustering engine.

- [x] **TASK-3.4: Incident Lifecycle State Machine & Severity Scoring**
  - **Description:** Manage incident transitions (`DETECTED` $\rightarrow$ `INVESTIGATING` $\rightarrow$ `IDENTIFIED` $\rightarrow$ `MITIGATED` $\rightarrow$ `RESOLVED`) and calculate severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`). Prohibit automated resolution.
  - **Dependencies:** TASK-3.3.
  - **Files/Modules:** `backend/app/incidents/state_machine.py`, `backend/app/models/incident.py`.
  - **Acceptance Criteria:** Severity correctly adjusts based on error magnitude; unauthorized state changes to `RESOLVED` are blocked.
  - **Tests:** `backend/tests/unit/test_incident_lifecycle.py`.
  - **Deliverable:** Incident state management service.

- [x] **TASK-3.5: Chronological Incident Timeline Generator**
  - **Description:** Generate structured incident progression timelines from the earliest trigger anomaly to cascading downstream errors.
  - **Dependencies:** TASK-3.3.
  - **Files/Modules:** `backend/app/incidents/timeline.py`.
  - **Acceptance Criteria:** Timeline events are strictly sorted chronologically with milestone annotations.
  - **Tests:** `backend/tests/unit/test_timeline.py`.
  - **Deliverable:** Milestone timeline generator.

---

## Phase 4: RAG and LLM Intelligence

- **Objective:** Ingest operational runbooks and historical post-mortems into `pgvector`, build vector retrieval, and implement evidence-grounded root cause analysis with mandatory log citations.
- **Estimated Duration:** Sprint 4

### Tasks:
- [x] **TASK-4.1: Runbook & Post-Mortem Document Ingestion**
  - **Description:** Create endpoints and background workers to parse Markdown and PDF runbooks, splitting text into recursive semantic chunks (500 tokens, 100 overlap).
  - **Dependencies:** TASK-1.3.
  - **Files/Modules:** `backend/app/rag/chunker.py`, `backend/app/models/rag.py`.
  - **Acceptance Criteria:** Documents are partitioned into chunks preserving section headers and document metadata.
  - **Tests:** `backend/tests/unit/test_chunker.py`.
  - **Deliverable:** Document chunking pipeline.

- [x] **TASK-4.2: OpenAI Embeddings & pgvector HNSW Indexing**
  - **Description:** Generate 1536-dimensional embeddings using OpenAI `text-embedding-3-small` and index chunks in PostgreSQL using `pgvector` HNSW index.
  - **Dependencies:** TASK-4.1.
  - **Files/Modules:** `backend/app/rag/embeddings.py`, `backend/app/rag/vector_store.py`.
  - **Acceptance Criteria:** Embeddings persist successfully; HNSW cosine similarity search returns relevant chunks in $< 50\text{ ms}$.
  - **Tests:** `backend/tests/unit/test_embeddings.py`, `backend/tests/unit/test_rag_vector_store.py`.
  - **Deliverable:** High-speed vector retrieval subsystem.

- [x] **TASK-4.3: OpenAI Client Wrapper with Circuit Breaker**
  - **Description:** Build resilient OpenAI client wrapper enforcing timeouts, exponential backoff retries, token bucket rate limits, and token usage cost tracking.
  - **Dependencies:** TASK-1.2.
  - **Files/Modules:** `backend/app/llm/client.py`.
  - **Acceptance Criteria:** API timeouts trigger retries; persistent failures trigger fallback handling without app crash.
  - **Tests:** `backend/tests/unit/test_embeddings.py`, `backend/tests/unit/test_rca_engine.py`.
  - **Deliverable:** Resilient LLM communication layer.

- [x] **TASK-4.4: Evidence-Grounded Root Cause Analysis Engine**
  - **Description:** Implement RCA reasoning engine that combines correlated incident logs and retrieved RAG runbooks, generating structured reports with mandatory `event_id` citations.
  - **Dependencies:** TASK-3.3, TASK-4.2, TASK-4.3.
  - **Files/Modules:** `backend/app/llm/rca_engine.py`, `backend/app/llm/prompts.py`.
  - **Acceptance Criteria:** Output conforms to Pydantic `RCAResponse`; all cited `event_id`s are verified against telemetry.
  - **Tests:** `backend/tests/unit/test_rca_engine.py`.
  - **Deliverable:** Factual, citation-backed RCA engine.

- [x] **TASK-4.5: AI Incident Investigation Assistant Endpoint**
  - **Description:** Build conversational API (`POST /api/v1/incidents/{incident_id}/chat`) allowing multi-turn Q&A over an incident's logs and historical knowledge base.
  - **Dependencies:** TASK-4.4.
  - **Files/Modules:** `backend/app/llm/assistant.py`, `backend/app/services/rca_service.py`, `backend/app/api/v1/endpoints/incidents.py`.
  - **Acceptance Criteria:** Assistant answers questions using verified log context and cites exact event records.
  - **Tests:** `backend/tests/unit/test_investigation_assistant.py`, `backend/tests/unit/test_rca_service.py`.
  - **Deliverable:** Conversational incident assistant API.

---

## Phase 5: Official Model Context Protocol (MCP) Server

- **Objective:** Implement a dedicated MCP server using the official Anthropic MCP Python SDK, exposing read-only incident investigation tools over STDIO and SSE transports.
- **Estimated Duration:** Sprint 5

### Tasks:
- [ ] **TASK-5.1: MCP Server Initialization & Transport Setup**
  - **Description:** Initialize the MCP server using `mcp.server.fastmcp`, configuring both STDIO transport (for local CLI/IDE) and SSE transport (for remote agents).
  - **Dependencies:** TASK-1.5.
  - **Files/Modules:** `backend/app/mcp/server.py`.
  - **Acceptance Criteria:** MCP client connects and successfully negotiates protocol capabilities.
  - **Tests:** `backend/tests/integration/test_mcp_handshake.py`.
  - **Deliverable:** Operational MCP server process.

- [ ] **TASK-5.2: Core MCP Log Investigation Tools**
  - **Description:** Register `search_logs`, `get_log_details`, and `analyse_error_pattern` tools with strongly typed Pydantic parameter schemas.
  - **Dependencies:** TASK-2.6, TASK-5.1.
  - **Files/Modules:** `backend/app/mcp/tools.py`.
  - **Acceptance Criteria:** External MCP client queries logs and receives structured JSON responses matching API contracts.
  - **Tests:** `backend/tests/integration/test_mcp_log_tools.py`.
  - **Deliverable:** Log querying MCP tools.

- [ ] **TASK-5.3: MCP Incident & Anomaly Tools**
  - **Description:** Register `detect_anomalies`, `get_incident_details`, `get_incident_timeline`, and `find_related_incidents` tools.
  - **Dependencies:** TASK-3.4, TASK-3.5, TASK-5.1.
  - **Files/Modules:** `backend/app/mcp/tools.py`.
  - **Acceptance Criteria:** Tools return incident metadata, timelines, and anomaly scores without mutating state.
  - **Tests:** `backend/tests/integration/test_mcp_incident_tools.py`.
  - **Deliverable:** Incident investigation MCP tools.

- [ ] **TASK-5.4: MCP Historical Search & Report Tools**
  - **Description:** Register `search_historical_incidents`, `get_service_health`, and `generate_incident_report` tools.
  - **Dependencies:** TASK-4.2, TASK-4.4, TASK-5.1.
  - **Files/Modules:** `backend/app/mcp/tools.py`.
  - **Acceptance Criteria:** External client executes semantic vector search and generates Markdown post-mortem reports.
  - **Tests:** `backend/tests/integration/test_mcp_report_tools.py`.
  - **Deliverable:** Complete 10-tool MCP suite.

---

## Phase 6: Frontend and Application Integration

- **Objective:** Develop the React 18 + TypeScript + Tailwind CSS dark-mode dashboard, featuring real-time incident monitoring, log exploration, interactive timeline visualization, and AI investigation chat.
- **Estimated Duration:** Sprint 6

### Tasks:
- [ ] **TASK-6.1: React Project Setup & Design System Tokens**
  - **Description:** Scaffold React 18 SPA with Vite, TypeScript, Tailwind CSS, Lucide icons, and Axios API client. Configure theme tokens matching `docs/DESIGN.md`.
  - **Dependencies:** TASK-1.6.
  - **Files/Modules:** `frontend/package.json`, `frontend/tailwind.config.js`, `frontend/src/index.css`.
  - **Acceptance Criteria:** Development server runs; dark mode theme tokens render accurately.
  - **Tests:** Frontend component test suite (`vitest`).
  - **Deliverable:** Modern frontend workspace with design system.

- [ ] **TASK-6.2: Overview Dashboard & Recharts Analytics**
  - **Description:** Build main dashboard displaying 4 KPI summary cards, time-series anomaly trend chart, active incident list, and service health status.
  - **Dependencies:** TASK-6.1, TASK-1.5.
  - **Files/Modules:** `frontend/src/pages/Overview.tsx`, `frontend/src/components/MetricCard.tsx`.
  - **Acceptance Criteria:** Charts render dynamically from backend API data with responsive resizing.
  - **Tests:** `frontend/src/pages/__tests__/Overview.test.tsx`.
  - **Deliverable:** Operational executive dashboard.

- [ ] **TASK-6.3: Incident Management & Detail Command Center**
  - **Description:** Build Incident List and 3-column Incident Detail View with status transition buttons, impacted service badges, and severity indicators.
  - **Dependencies:** TASK-6.1, TASK-3.4.
  - **Files/Modules:** `frontend/src/pages/Incidents.tsx`, `frontend/src/pages/IncidentDetail.tsx`.
  - **Acceptance Criteria:** Engineers can view details, change status to `INVESTIGATING`, and review severity.
  - **Tests:** `frontend/src/pages/__tests__/IncidentDetail.test.tsx`.
  - **Deliverable:** Full incident triage interface.

- [ ] **TASK-6.4: Interactive Incident Timeline Visualizer**
  - **Description:** Develop interactive horizontal and vertical timeline component showing chronological event progression with clickable milestone nodes.
  - **Dependencies:** TASK-6.3, TASK-3.5.
  - **Files/Modules:** `frontend/src/components/IncidentTimeline.tsx`.
  - **Acceptance Criteria:** Cascading multi-service milestones render in exact chronological order.
  - **Tests:** Visual regression and component unit test.
  - **Deliverable:** Interactive timeline visualizer.

- [ ] **TASK-6.5: Log Explorer with Syntax Highlighting**
  - **Description:** High-density log viewer with search, facet filters, expandable JSON metadata, and stack trace view with copy actions.
  - **Dependencies:** TASK-6.1, TASK-2.6.
  - **Files/Modules:** `frontend/src/pages/LogExplorer.tsx`, `frontend/src/components/LogTable.tsx`.
  - **Acceptance Criteria:** Renders 1,000+ log lines smoothly; clicking `event_id` copies ID or filters view.
  - **Tests:** `frontend/src/pages/__tests__/LogExplorer.test.tsx`.
  - **Deliverable:** Fast, developer-friendly log browser.

- [ ] **TASK-6.6: AI Investigation Chat & RCA Panel**
  - **Description:** Integrate conversational chat drawer with streaming AI responses, markdown rendering, clickable log citations, and safe diagnostic command boxes.
  - **Dependencies:** TASK-6.3, TASK-4.4, TASK-4.5.
  - **Files/Modules:** `frontend/src/components/AIAssistantDrawer.tsx`, `frontend/src/components/RCAPanel.tsx`.
  - **Acceptance Criteria:** Clicking citation pill highlights cited log event in center viewer; copy button copies diagnostic commands.
  - **Tests:** `frontend/src/components/__tests__/AIAssistant.test.tsx`.
  - **Deliverable:** Evidence-first AI investigation interface.

---

## Phase 7: Production Readiness and Hardening

- **Objective:** Finalize end-to-end integration, performance benchmarking on large files, security hardening, automated CI/CD pipeline verification, and comprehensive operational documentation.
- **Estimated Duration:** Sprint 7

### Tasks:
- [ ] **TASK-7.1: Large Log File Benchmark ($100\text{ MB}$ / 500,000 lines)**
  - **Description:** Execute benchmark suite measuring streaming ingestion throughput, memory ceiling ($\le 200\text{ MB}$), and database insertion latency.
  - **Dependencies:** All previous phases.
  - **Files/Modules:** `scripts/benchmark_ingestion.py`.
  - **Acceptance Criteria:** Sustained throughput $\ge 5,000\text{ events/sec}$; resident memory remains below $200\text{ MB}$.
  - **Tests:** Automated benchmark run with assertion checks.
  - **Deliverable:** Performance verification report.

- [ ] **TASK-7.2: Test Coverage Hardening ($\ge 90\%$)**
  - **Description:** Audit backend test suite branch and statement coverage; write unit and integration tests for edge cases to exceed $90\%$ overall coverage.
  - **Dependencies:** All backend tasks.
  - **Files/Modules:** `backend/tests/`.
  - **Acceptance Criteria:** `pytest --cov=app --cov-report=term-missing --cov-fail-under=90` passes.
  - **Tests:** Complete Pytest test suite.
  - **Deliverable:** Audited, high-coverage test suite.

- [ ] **TASK-7.3: Security & Vulnerability Auditing**
  - **Description:** Run Bandit static security analysis, pip-audit for dependency vulnerabilities, and npm audit on frontend packages.
  - **Dependencies:** TASK-1.1, TASK-6.1.
  - **Files/Modules:** Entire repository.
  - **Acceptance Criteria:** Zero critical or high-severity vulnerabilities reported.
  - **Tests:** Bandit and pip-audit execution.
  - **Deliverable:** Clean security audit report.

- [ ] **TASK-7.4: CI/CD Pipeline Verification**
  - **Description:** Validate GitHub Actions workflows (`ci.yml` and `pr-audit.yml`) ensuring automated linting, type checks, tests, security scans, and Docker builds pass.
  - **Dependencies:** All tasks.
  - **Files/Modules:** `.github/workflows/ci.yml`, `.github/workflows/pr-audit.yml`.
  - **Acceptance Criteria:** Clean green run across all workflow jobs on pull requests.
  - **Tests:** GitHub Actions CI run.
  - **Deliverable:** Production-grade CI/CD automation.

- [ ] **TASK-7.5: Final Demo Seed Dataset & Runbook Showcase**
  - **Description:** Provide synthetic multi-service outage logs (e.g., e-commerce payment gateway timeout cascading to order service) and runbooks for demonstration.
  - **Dependencies:** All tasks.
  - **Files/Modules:** `scripts/seed_demo_data.py`, `docs/runbooks/sample_db_pool_saturation.md`.
  - **Acceptance Criteria:** Running the seed script populates a realistic incident with working timeline, anomalies, RAG runbooks, and verified RCA report.
  - **Tests:** E2E demonstration verification.
  - **Deliverable:** Turnkey portfolio demonstration environment.
