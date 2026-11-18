## 📌 Summary of Changes

<!-- Provide a concise 2-4 sentence summary of the architectural changes, features, or fixes introduced in this pull request. -->

---

## 🎯 Motivation and Context

<!-- Why is this change required? What operational problem or ticket does it solve? If applicable, link related issues. -->
Related Issue: Fixes #<!-- issue number -->

---

## 🏷️ Type of Change

<!-- Please check all that apply: -->
- [ ] `feat`: A new feature or subsystem enhancement
- [ ] `fix`: A bug fix in log processing, anomaly math, correlation, or APIs
- [ ] `refactor`: Code change that neither fixes a bug nor adds a feature
- [ ] `perf`: A code change that improves throughput or reduces latency
- [ ] `docs`: Documentation updates, PRD, architecture, or design updates
- [ ] `test`: Adding missing tests or correcting existing tests
- [ ] `chore`: Maintenance, dependencies, Docker, or CI/CD workflow updates

---

## 💥 Breaking Changes

- [ ] **No breaking changes** introduced.
- [ ] **Breaking change** (fix or feature that would cause existing functionality or schemas to change).
  *If yes, describe the migration or backward compatibility path:*

---

## 🏛️ Architectural & Subsystem Impact

<!-- Check all impacted subsystems and describe changes if applicable: -->
- [ ] **Log Ingestion & Parsing:** Changes to canonical schema, format parsers, or normalizer.
- [ ] **Statistical Anomaly Detection:** Changes to baseline calculation, Z-scores, IQR, or Isolation Forest.
- [ ] **Incident Correlation:** Changes to grouping logic, temporal burst windows, or state machines.
- [ ] **RAG & Knowledge Base:** Changes to chunking, embeddings, or `pgvector` HNSW queries.
- [ ] **LLM & RCA Engine:** Changes to prompt templates, response parsing, or citation verification.
- [ ] **MCP Server:** Changes to tool registrations, parameter schemas, or transport layers.
- [ ] **Database & Migrations:** New tables, column alterations, or Alembic revision scripts.
- [ ] **Frontend Presentation:** Changes to dashboard, telemetry charts, or investigation UI.

---

## 🔒 Security Considerations

<!-- Address security guardrails: -->
- [ ] Input validation applied via Pydantic v2 schemas.
- [ ] Untrusted log inputs properly encapsulated inside prompt delimiters.
- [ ] File uploads validated for MIME types, magic bytes, and size ceilings ($100\text{ MB}$).
- [ ] PII and credentials masked before persistence.
- [ ] No hardcoded secrets, API keys, or credentials committed.
- [ ] Static security scans (`bandit`, `pip-audit`) pass with zero high/critical findings.

---

## 🧪 Testing Performed

<!-- Describe the tests you ran to verify your changes. Include commands used: -->
- **Test Command Executed:** `pytest --cov=app --cov-report=term-missing --cov-fail-under=90`
- **Coverage Result:** `XX.X%`
- **Manual Verification:** (e.g., Docker Compose startup, MCP tool invocation, log upload test)

---

## ✅ Quality Checklist

Please ensure all checks pass before submitting for review:

- [ ] My code adheres to the engineering rules specified in **[docs/RULES.md](docs/RULES.md)**.
- [ ] Code is formatted and linted cleanly with `ruff check .` and `ruff format --check .`.
- [ ] Strict type checking passes with `mypy backend` (zero errors).
- [ ] Unit tests added or updated for all new logic.
- [ ] Integration tests added for API endpoints or database queries where required.
- [ ] Overall test branch/line coverage meets or exceeds **90%**.
- [ ] No secrets or sensitive test logs are committed to git.
- [ ] Database migrations tested in both upgrade and downgrade directions (`alembic upgrade head && alembic downgrade base`).
- [ ] AI prompt outputs and citation verification verified for hallucination prevention.
- [ ] Relevant documentation in `docs/` (`PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `MEMORY.md`) updated.
- [ ] Docker builds verified locally via `docker compose build`.
