# TraceMind AI — Backend Core Service

This directory contains the core backend services, FastAPI application, domain processing engines, and testing infrastructure for **TraceMind AI**.

## Directory Layout

```
backend/
├── app/
│   ├── main.py              # Application factory & router registration
│   ├── api/                 # REST endpoints and dependency injection
│   ├── core/                # Configuration, logging, database, security
│   ├── log_processing/      # Format parsers, normalizers, fingerprinter
│   ├── anomaly_detection/   # Baseline calculations & statistical detectors
│   ├── incidents/           # Multi-dimensional correlation & timeline engine
│   ├── rag/                 # Text chunking, pgvector embedding retrieval
│   ├── llm/                 # OpenAI client wrapper & structured RCA engine
│   ├── mcp/                 # Official Python Model Context Protocol server
│   ├── models/              # SQLAlchemy 2.0 database entities
│   ├── schemas/             # Pydantic v2 input & output contracts
│   └── services/            # Business logic orchestration
└── tests/                   # Unit and integration test suites
```

## Local Development

```bash
# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install in editable mode with development dependencies
pip install -e ".[dev]"

# Run Ruff linter and formatter
ruff check .
ruff format --check .

# Run strict type checking
mypy app

# Execute test suite with 90%+ coverage enforcement
pytest --cov=app --cov-report=term-missing --cov-fail-under=90
```
