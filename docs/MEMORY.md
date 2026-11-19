# TraceMind AI — Living Project Journal & Architectural Decision Records (ADRs)

| **Journal Metadata** | **Specification** |
| :--- | :--- |
| **System** | **TraceMind AI Incident Intelligence Platform** |
| **Document Version** | 1.0.0-PROD |
| **Author** | Anmol Vishvas ([anmol23vishvas@gmail.com](mailto:anmol23vishvas@gmail.com)) |
| **Target Repository** | [https://github.com/anmolvishvas/TraceMind-AI](https://github.com/anmolvishvas/TraceMind-AI) |
| **Current Status** | Foundation, Architecture, & CI/CD Bootstrap Phase (Phase 1 Ready) |
| **Last Updated** | November 2026 |

---

## 1. Project Overview & Current State

TraceMind AI is a production-grade, portfolio-defining incident intelligence and root cause analysis platform. It combines high-throughput streaming log normalization, deterministic statistical anomaly detection (Z-score, IQR, Isolation Forest), multi-dimensional incident correlation, official Model Context Protocol (MCP) tool integration, and evidence-grounded Retrieval-Augmented Generation (RAG) using PostgreSQL and `pgvector`.

### Current Development Status
- **Current Phase:** **All 7 Production Phases Completed (100% Production Ready)**
- **Completed Milestones:**
  - Complete architecture, PRD, engineering rulebook, UI/UX specification, implementation roadmap, and living journal authored in `docs/`.
  - Brand assets and official logo integrated (`assets/logo.png`).
  - Production GitHub Actions CI/CD workflows authored (`.github/workflows/ci.yml`, `.github/workflows/pr-audit.yml`).
  - Pull Request #1 successfully merged into `main` with 100% green checks across all 6 CI matrix jobs.
  - Pull Request #2 merged into `main` with full async database, Redis pool, domain exceptions, and readiness health probes.
  - Pull Request #3 merged into `main` delivering streaming multi-format log parsing, PII scrubber, deterministic error fingerprinter, and micro-batch persistence.
  - Pull Request #4 merged into `main` delivering pure numerical statistical anomaly detection (Z-score, IQR, Isolation Forest, Ensemble), multi-dimensional incident correlation, human-in-the-loop state machine, and timeline generation.
  - Pull Request #5 merged into `main` delivering RAG knowledge base, pgvector HNSW cosine similarity search, resilient OpenAI client, evidence-grounded RCA engine with mandatory citations, and interactive copilot assistant.
  - Pull Request #6 merged into `main` delivering official Model Context Protocol (MCP) server built with Python MCP SDK exposing 10 read-only operational tools over STDIO and SSE.
  - Pull Request #7 merged into `main` delivering React 18 production dashboard with TypeScript, Tailwind CSS, Recharts analytics, incident timeline explorer, live log stream viewer with file upload, and RAG knowledge search.
  - **Phase 7 Completed (Production Readiness, Benchmarking & Turnkey Demo):**
    - High-throughput streaming ingestion benchmark (`scripts/benchmark_ingestion.py`) validating > 18,000 events/second parsing throughput with sub-second latency.
    - Automated demo dataset seeding script (`scripts/seed_demo_data.py`) populating realistic distributed failure telemetry, correlated incidents, and pgvector runbook embeddings.
    - Verified production operational runbook (`docs/runbooks/sample_db_pool_saturation.md`).
    - Full security audit passed (Bandit, pip-audit, npm audit).
    - 100% green GitHub Actions CI automation across all 8 matrix jobs.

---

## 2. Active Implementation Status

| Milestone / Subsystem | Phase | Status | Primary Owner | Target Delivery |
| :--- | :--- | :--- | :--- | :--- |
| **Foundation & Scaffolding** | Phase 1 | 🟢 Done | Architecture / DevOps | Sprint 1 |
| **Log Ingestion & Parsing** | Phase 2 | 🟢 Done | Backend / Data | Sprint 2 |
| **Statistical Anomaly & Correlation**| Phase 3 | 🟢 Done | ML / SRE | Sprint 3 |
| **RAG & LLM RCA Engine** | Phase 4 | 🟢 Done | AI / Backend | Sprint 4 |
| **Official Python MCP Server** | Phase 5 | 🟢 Done | AI / Integration | Sprint 5 |
| **React Dashboard & UI** | Phase 6 | 🟢 Done | Frontend / Design | Sprint 6 |
| **Production Readiness & Hardening**| Phase 7 | 🟢 Done | SRE / Security | Sprint 7 |

*Status Legend:* 🟢 Done | 🟡 In Progress | ⚪ Pending | 🔴 Blocked

---

## 3. Known Technical Limitations & Constraints

1. **File Upload Payload Boundary:** The initial REST API multipart file upload is capped at $100\text{ MB}$ per file in the MVP. Files exceeding $100\text{ MB}$ must be compressed (`.gz`) or ingested via the streaming daemon planned in Phase 7.
2. **PostgreSQL Vector Scale:** `pgvector` with HNSW indexes provides sub-50ms search for collections up to several million vectors. Beyond 50 million document chunks, partitioned tables or dedicated vector nodes will be required.
3. **LLM Context Window Ceiling:** To prevent context overflow and excessive token costs, log context passed to the LLM during RCA is strictly capped at the top 30 most representative log events and top 5 RAG chunks.
4. **Third-Party API Dependency:** The LLM RCA subsystem relies on OpenAI API connectivity. Circuit breakers and local mock fallbacks are enforced during testing and network disruptions.

---

## 4. Architectural Decision Records (ADRs)

---

### ADR-001: Selection of FastAPI & Python 3.12+ for Core Backend
- **Status:** **ACCEPTED**
- **Date:** November 2026
- **Context:** TraceMind AI requires high concurrency for handling asynchronous log streams and API requests, combined with native integration with modern ML (`scikit-learn`), vector databases (`pgvector`), and the official Anthropic MCP Python SDK.
- **Decision:** Use Python 3.12+ with the FastAPI framework, Starlette, Uvicorn, and Pydantic v2.
- **Alternatives Considered:**
  - *Go (Gin/Fiber):* Exceptional concurrency and low memory footprint, but lacks native libraries for scientific anomaly detection, deep RAG chunking utilities, and direct support for the official Python MCP SDK.
  - *Django Ninja:* Feature-rich, but heavier ORM overhead and less idiomatic asynchronous streaming paradigms compared to FastAPI.
  - *Node.js / NestJS:* Excellent async I/O, but suboptimal ecosystem for numerical anomaly detection and data science operations.
- **Consequences:** Provides rapid development velocity, native Pydantic v2 validation, automatic OpenAPI generation, and unified language across data pipelines and APIs. Requires discipline in ensuring all database and network I/O is non-blocking.

---

### ADR-002: PostgreSQL 16 with pgvector for Relational Data and Vector Search
- **Status:** **ACCEPTED**
- **Date:** November 2026
- **Context:** The platform requires relational data persistence (users, incidents, timelines, log events, correlation rules) and dense vector embeddings (1536-dimensional vectors for runbooks and historical post-mortems).
- **Decision:** Utilize PostgreSQL 16 with the native `pgvector` extension and HNSW (Hierarchical Navigable Small World) indexing.
- **Alternatives Considered:**
  - *Standalone Vector DBs (Pinecone, Qdrant, Weaviate) + Relational DB:* Introduces two database systems, distributed transactions, consistency lag, and operational complexity.
  - *Elasticsearch / OpenSearch:* Strong for keyword search, but higher operational overhead, heavy JVM memory footprints, and less efficient native vector similarity compared to `pgvector` HNSW.
- **Consequences:** Eliminates architectural fragmentation. Enables ACID transactions across both structured metadata and vector embeddings within a single database instance. Simplifies local Docker Compose development.

---

### ADR-003: Redis for Caching, Rate Limiting, and Asynchronous Job Queue Coordination
- **Status:** **ACCEPTED**
- **Date:** November 2026
- **Context:** Anomaly detection relies on calculating rolling error frequencies across 1-minute, 5-minute, and 15-minute sliding windows. Heavy write loads during log ingestion require high-speed atomic increments and distributed task queuing.
- **Decision:** Deploy Redis 7.2-alpine as an in-memory cache, rate limiter, rolling metrics counter, and message broker for background workers.
- **Alternatives Considered:**
  - *PostgreSQL Polling / LISTEN-NOTIFY:* Inefficient for high-frequency sub-second metric increments ($5,000+\text{ events/sec}$).
  - *Apache Kafka / RabbitMQ:* Outstanding streaming brokers, but introduces heavy operational infrastructure overkill for MVP deployment.
- **Consequences:** Delivers sub-millisecond atomic counter increments (`INCRBY`, `ZADD`) for sliding windows. Provides a reliable, lightweight task queue. Requires memory sizing controls and AOF persistence configuration.

---

### ADR-004: Decoupling Statistical Anomaly Detection from LLM Inference
- **Status:** **ACCEPTED**
- **Date:** November 2026
- **Context:** LLMs are non-deterministic, expensive per call, subject to latency spikes (1-5 seconds), and notoriously unreliable when evaluating numerical distributions and calculating metric deviations.
- **Decision:** All numerical anomaly detection (Z-score calculation, Interquartile Range, Isolation Forest) must be executed exclusively by deterministic Python algorithms (`numpy`, `scikit-learn`, `scipy`). Under no circumstances is an LLM prompted to evaluate whether a metric spike is anomalous.
- **Alternatives Considered:**
  - *Prompting LLMs with Raw Time-Series Data:* Costly, slow, and produces severe hallucination rates where the LLM fabricates spikes or overlooks statistically significant departures.
- **Consequences:** 100% deterministic anomaly evaluation with sub-10ms execution times. Zero LLM API token costs for metric analysis. Guarantees that alerts reflect verifiable mathematical facts.

---

### ADR-005: Dedicated Deterministic Incident Correlation Engine with Graph-Based Cascading Analysis
- **Status:** **ACCEPTED**
- **Date:** November 2026
- **Context:** When a microservice fails, cascading errors ripple across downstream consumers. Grouping related log lines into a single incident must be deterministic and transparent.
- **Decision:** Implement a dedicated rule-based and graph-weighted correlation engine (`app/incidents/correlator.py`). The engine evaluates shared trace IDs, correlation IDs, temporal burst adjacency, and service dependency topology to cluster events into an `Incident` entity.
- **Alternatives Considered:**
  - *Clustering via Unsupervised Embeddings (HDBSCAN/DBSCAN on log text embeddings):* Prone to false groupings where unrelated errors with similar wording (e.g., generic `NullPointerException`) are erroneously merged.
- **Consequences:** Clear audit trail explaining *why* logs were grouped. Explicitly categorizes linkages as `CONFIRMED_CAUSAL`, `TOPOLOGICAL_CORRELATION`, or `INFERRED_TEMPORAL`.

---

### ADR-006: Model Context Protocol (MCP) as an Isolated Presentation Boundary
- **Status:** **ACCEPTED**
- **Date:** November 2026
- **Context:** External AI development agents (Cursor, Claude Desktop, Antigravity IDE) need to query TraceMind AI's incident database, logs, and anomaly reports.
- **Decision:** Build a dedicated MCP server using the official Anthropic MCP Python SDK (`mcp`). The MCP server acts as an isolated presentation adapter that imports and calls the exact same underlying application service layer (`app/services/`) used by the FastAPI REST routes.
- **Alternatives Considered:**
  - *Custom REST API Plugins / Webhooks:* Lacks standard AI client tool-calling conventions and requires custom client-side glue code.
  - *Embedding MCP Logic Directly in Route Handlers:* Violates separation of concerns and duplicates validation logic.
- **Consequences:** Zero duplication of business logic. External AI clients gain instant, strongly typed, read-only access to TraceMind AI's operational tools over STDIO or SSE.

---

### ADR-007: Evidence-First RAG Architecture with Mandatory Source Citations and Zero-Resolution Auto-Claim
- **Status:** **ACCEPTED**
- **Date:** November 2026
- **Context:** In high-stakes production incidents, incorrect or hallucinatory AI recommendations can lead to catastrophic outages or data loss.
- **Decision:** 
  1. All LLM-generated root cause hypotheses must cite verified database `event_id` records and runbook section titles.
  2. The backend validates cited `event_id` records against PostgreSQL before displaying the report.
  3. The platform is architecturally forbidden from automatically transitioning an incident to `RESOLVED` or running remediation commands autonomously.
- **Alternatives Considered:**
  - *Unconstrained Conversational Generation:* Generates smooth explanations but frequently invents non-existent database queries or false error timestamps.
  - *Autonomous Self-Healing Execution:* High risk of runaway failures or destructive modifications in production clusters.
- **Consequences:** High engineer trust and verifiable factual grounding. Human-in-the-loop sign-off remains mandatory for all state transitions and remediation actions.

---

### ADR-008: Docker and Docker Compose Multi-Stage Containerization Strategy
- **Status:** **ACCEPTED**
- **Date:** November 2026
- **Context:** TraceMind AI consists of multiple coordinated services: PostgreSQL + pgvector, Redis, FastAPI backend, background workers, and React frontend. Developers and CI pipelines need a 100% reproducible, single-command startup.
- **Decision:** Containerize all components using multi-stage Dockerfiles (non-root `appuser`, minimal base images) and orchestrate local development and CI verification via `docker-compose.yml`.
- **Alternatives Considered:**
  - *Local Native Installation (bare-metal Postgres/Redis):* Subject to environment discrepancies across developer operating systems (Windows, macOS, Linux).
  - *Local Kubernetes (Minikube / Kind):* High resource overhead and unnecessary complexity for local development.
- **Consequences:** Complete environment isolation. Developers can spin up the full stack via `docker compose up --build`. Multi-stage builds keep production image sizes minimal ($< 150\text{ MB}$ for backend, $< 30\text{ MB}$ for frontend Nginx).

---

## 5. Immediate Next Actions

1. Commit and push foundational documentation, architecture, CI/CD pipelines, and configuration files.
2. Initialize GitHub Pull Request #1 targeting `main`.
3. Proceed with Phase 1 execution:
   - Implement `app/core/config.py` (Pydantic v2 Settings).
   - Configure `app/core/database.py` (SQLAlchemy asyncpg + pgvector extension check).
   - Author initial health check integration tests.
