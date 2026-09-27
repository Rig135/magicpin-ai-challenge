# magicpin AI Challenge — Merchant AI Assistant "Vera"

An intelligent AI assistant designed to engage local retail and dining merchants on magicpin, offering personalized insights, context-aware suggestions, proactive notifications, and seamless conversational workflows.

---

## 🏛️ Architecture Overview

The assistant is built with **FastAPI** following a modular, layered architecture:

```
├── app/
│   ├── api/             # API routes and request handlers
│   │   └── routes.py    # /v1/healthz, /v1/metadata, /v1/context, /v1/tick, /v1/reply
│   ├── models/          # Pydantic schemas for request/response validation
│   │   └── schemas.py
│   ├── store/           # State management with optimistic versioning
│   │   ├── context_store.py
│   │   └── conversation_store.py
│   ├── services/        # Business logic & LLM composition engines
│   ├── config.py        # Environment variables & runtime settings
│   └── main.py          # FastAPI application entry point
├── dataset/             # Category definitions and seed data for merchants/triggers
├── tests/               # Test suites (unit, integration, lifecycle)
├── judge_simulator.py   # Benchmark evaluation runner
└── requirements.txt     # Python dependencies
```

---

## 🚀 Key Features (Phase 1)

1. **State & Context Ingestion (`POST /v1/context`)**:
   - Atomic in-memory key-value context storage keyed by `(scope, context_id)`.
   - Strict versioning semantics: accepts new monotonic versions, rejects stale updates, and treats duplicate versions as idempotent.
   - Dynamic tracking of registered categories, merchants, customers, and triggers.

2. **Simulation Lifecycle (`POST /v1/tick`, `POST /v1/reply`)**:
   - `POST /v1/tick`: Receives incoming trigger events and advances simulation state.
   - `POST /v1/reply`: Multi-turn conversational interaction endpoint with conversation history tracking.

3. **Observability & Metadata (`GET /v1/healthz`, `GET /v1/metadata`)**:
   - Healthcheck endpoint providing uptime and system status.
   - Metadata endpoint reporting team details, active model, and approach configuration.

---

## 📦 Installation & Setup

### Prerequisites
- Python 3.10+
- Virtual environment (recommended)

### Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🧪 Running Tests

Run the full test suite using `pytest`:
```bash
pytest tests/ -v
```

---

## 🏃 Running the Service

Start the FastAPI server on port 8080:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Verify endpoints:
```bash
# Healthcheck
curl http://localhost:8080/v1/healthz

# Metadata
curl http://localhost:8080/v1/metadata
```

---

## ⚖️ Running the Judge Simulator

The repository includes the benchmark evaluation runner (`judge_simulator.py`):
```bash
python3 judge_simulator.py
```
*(Configure `BOT_URL`, `LLM_PROVIDER`, and `LLM_API_KEY` inside `judge_simulator.py` or via environment variables before running).*
