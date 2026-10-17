# Architecture

## Overview

Atlas Studio is a local-first AI job-application framework: a FastAPI backend
serving a React+Vite SPA. The deterministic core (TF-IDF relevance scoring)
runs entirely offline with no LLM dependency. LLM-generated explanations are
opt-in and advisory.

## Data flow

```
User (browser, localhost:5173)
  |  typed fetch() with credentials: "include" (HttpOnly SameSite cookie + x-csrf-token)
  v
FastAPI backend (localhost:8000)
  |  Auth: session cookie (HttpOnly) -> CurrentUser -> require_role
  |  DB: async SQLAlchemy + aiosqlite (sqlite://…/atlas_studio.db)
  |
  |--- /api/postings          CRUD import/list/get/update/delete; lifecycle fetch
  |--- /api/scoring/run       sweep past deadlines -> expired, fetch+score candidates
  |--- /api/scoring/sweep     explicit retire to expired (terminal)
  |--- /api/scoring/evaluate  IR metrics over data/labeled_postings.json
  |--- /api/scoring/explain   opt-in LLM explanation (needs LLM_API_KEY)
  |
  v
TFIDFScorer (deterministic, no network)
  tokenize -> corpus IDF -> TF-IDF vectors -> cosine similarity -> [0,1] score

[opt-in] LLMAdvisor -> provider adapter (OpenAI / Anthropic / Gemini / Ollama) via httpx
```

## File layout

```
backend/
  app/main.py              FastAPI factory (create_app), lifespan, health/version
  app/api/auth.py          demo login, logout, me, roles
  app/api/postings.py      posting CRUD + manual fetch + audit log
  app/api/scoring.py       run / sweep / evaluate / explain endpoints
  app/api/deps.py          DB + role dependencies (viewer/analyst/admin)
  app/core/config.py       pydantic-settings (env-driven, no committed secrets)
  app/core/database.py     async session/engine, schema init
  app/core/security.py     sessions, CSRF, role hierarchy
  app/models/orm.py        Posting, ScoringRun, AuditLog, LabelingExample
  app/models/schemas.py    Pydantic request/response schemas
  app/services/scorer.py   deterministic TF-IDF + cosine scorer + IR metrics
  app/services/lifecycle.py posting lifecycle: sweep / select / run_scoring_round
  app/services/llm.py      opt-in LLM explainer with httpx provider adapters
  tests/                   pytest suite (auth, posting, scoring, lifecycle)
frontend/
  src/api/client.ts        typed fetch client (cookie auth + CSRF)
  src/components/           dashboard, posting card, import/score panels
  src/pages/               PostingsPage, ScoringPage
  src/*test*.tsx           vitest + Testing Library component tests
data/labeled_postings.json  scorer evaluation fixture (10 examples, 5 relevant)
```

## Lifecycle state machine

```
new ──fetch+score──> scored        (terminal for this run)
  └──fetch fails──> fetch_failed   (retryable, retry_count < max_retries)
  └──deadline pass──> expired      (terminal — only the sweep writes this)

Candidates for a scoring round: new
  OR (fetch_failed AND retry_count < max_retries).
```

See `backend/app/services/lifecycle.py` for the engine and
`backend/tests/test_lifecycle.py` for the issue-#534 semantics.