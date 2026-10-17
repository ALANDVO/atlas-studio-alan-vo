# Atlas Studio — Alan Vo | AI & Machine Learning

> Work in progress. This checkpoint may be incomplete or fail tests. See PLAN.md and STATUS.md before use.


A local-first AI job-application framework. Job seekers import job postings,
score relevance against a target role profile with a deterministic TF-IDF
cosine-similarity engine, and track the full application lifecycle. The core
scorer runs offline with **no LLM key required**; LLM-generated explanations
are opt-in and advisory only. Built for developers who want to own their job
search pipeline on their own machine.

---

## Problem

Job postings get lost after a transient fetch failure (404, 403, timeout, login
wall): the failure is indistinguishable from a genuinely closed posting, so the
entry is abandoned and never retried ([issue #534](https://github.com/MadsLorentzen/ai-job-search/issues/534)).
Atlas Studio models this as two distinct statuses:

| Status        | Retryable | Terminal | Meaning                          |
|---------------|-----------|----------|----------------------------------|
| `new`         | yes       | no       | imported, not yet scored         |
| `fetch_failed`| yes       | no       | transient fetch error, < max_retries |
| `scored`      | no        | no       | fetched + scored with a 0–1 score |
| `expired`     | no        | yes      | deadline passed / page closed    |

A failed fetch is recorded as `fetch_failed` and re-selected on the next run
until the retry cap is reached. Only the **sweep** retires a posting to
`expired`, and only when its deadline has actually passed.

## Feature: relevance scoring

The domain engine is a deterministic TF-IDF + cosine-similarity scorer
(`backend/app/services/scorer.py`):

1. Tokenize the posting text and the target role profile (lowercase, accent
   folding, stop-word removal).
2. Build corpus-derived IDF from all posting texts + the target profile.
3. Compute TF-IDF vectors and cosine similarity between the target and each
   posting.
4. Normalize to a `[0, 1]` score and report the matched terms that drove it.

No model weights, no network, no key — the same input always yields the same
score.

## Workflows

1. **Posting pipeline** — import postings (`POST /api/postings`), run a scoring
   round (`POST /api/scoring/run`) which sweeps past-deadline postings to
   `expired`, fetches content, scores each posting, and persists status with
   fetch metadata. Retryable `fetch_failed` postings are re-attempted on the
   next run.
2. **Scorer evaluation** — `GET /api/scoring/evaluate` scores a labeled
   fixture and reports IR metrics (Precision@k, Recall@k, MAP, NDCG@k).
3. **Opt-in LLM explanation** — `POST /api/scoring/explain` produces an advisory
   natural-language justification, grounded in the TF-IDF matched terms.
   Without `LLM_API_KEY` it returns a clear `501` error — it never fabricates a
   response.

> Application-tracking and CV-tailoring workflows are planned milestones, not
> yet implemented. See [PLAN.md](PLAN.md).

## Architecture

```
┌────────────────┐      ┌─────────────────┐     ┌──────────────┐
│  React + Vite  │ HTTP │  FastAPI app    │ DB  │  SQLite      │
│  (port 5173)   │───┬──│  (port 8000)    │─────│  persistent   │
└────────────────┘   │  └────────┬─────────┘     └──────────────┘
                     │           │
                     │  ┌────────┴────────┐
                     │  │  TF-IDF Scorer  │   (deterministic, offline)
                     │  │  cosine sim     │
                     │  └─────────────────┘
                     │  ┌───────────────────────────┐
                     │  │  Opt-in LLM Explainer      │  (httpx adapters)
                     │  │  OpenAI / Anthropic /      │
                     │  │  Gemini / Ollama           │
                     │  └───────────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for the data flow and
[docs/auth.md](docs/auth.md) for the authentication model.

## Install

```bash
# Backend (requires Python 3.12)
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# Frontend (requires Node 24)
cd frontend
npm install
cd ..
```

## Run locally (demo auth)

```bash
# Terminal 1 — backend (localhost-only, demo auth on)
AUTH_DEMO_MODE=true PYTHONPATH=backend .venv/bin/uvicorn app.main:create_app \
  --factory --host 127.0.0.1 --port 8000

# Terminal 2 — frontend dev server
cd frontend && npm run dev
```

Demo login: `POST /auth/demo?role=analyst` issues an `atlas_session` HttpOnly
`SameSite=Lax` cookie and a CSRF token. All data endpoints require a session;
write endpoints additionally require the `x-csrf-token` header.

> `AUTH_DEMO_MODE` is refused when `ENVIRONMENT=production`. See
> [docs/auth.md](docs/auth.md). Production uses OIDC authorization-code login
> via Keycloak (planned milestone).

## Run with Docker

```bash
docker compose up --build     # backend + frontend, demo auth
docker compose --profile auth up --build   # + Keycloak (OIDC)
docker compose --profile tls up --build    # + Caddy TLS reverse proxy
```

The backend persists data under `data/` (mounted volume in compose).

## Test

```bash
# Backend
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests

# Frontend
cd frontend && npm test -- --run
```

Backend tests mock all provider/network calls and cover the scorer, lifecycle
(issue #534 semantics), auth (unauthenticated rejection + role denial), the
postings API, and the scoring API over a real ASGI/HTTP boundary. Frontend
tests cover the StatusBadge, PostingsDashboard, and ImportDialog components.

## AI/ML evaluation

The TF-IDF scorer is evaluated against a small hand-authored labeled fixture,
`data/labeled_postings.json` (10 examples, 5 relevant to the "Machine Learning
Engineer" target profile). No network is required.

Reproducible command:

```bash
curl -s -c cookies.txt -X POST "http://127.0.0.1:8000/auth/demo?role=analyst" > /dev/null
curl -s -b cookies.txt "http://127.0.0.1:8000/api/scoring/evaluate"
```

**Data provenance:** `data/labeled_postings.json` — 10 synthetic job-posting
snippets (5 relevant, 5 not), authored to mirror real ML/engineering/MLOps
postings.

**Baseline (measured, deterministic):**

| Metric      | Value |
|-------------|-------|
| Precision@3 | 1.0   |
| Recall@3    | 0.6   |
| NDCG@3      | 1.0   |
| MAP         | 0.967 |
| NDCG@10     | 0.990 |

Top-3 by score: `Machine Learning Engineer` (0.53), `MLOps Engineer` (0.42),
`Senior Data Scientist` (0.25) — all relevant.

**Failure cases / limitations:** the scorer is term-based and has no
understanding of semantics or negation. Synonyms expressed with different
words ("ML" vs "machine learning") and postings whose relevant content is
phrased unlike the target profile score lower. It does not learn from data;
`Precision@10` (0.5) reflects the expected tail of non-relevant documents ranked
by keyword overlap alone. These are boundaries of the deterministic baseline,
not bugs.

## Provider configuration (opt-in LLM explanation)

| Variable        | Default              | Notes                                   |
|------------------|----------------------|-----------------------------------------|
| `LLM_API_KEY`    | _(unset, required)_  | Only secret; server-side only           |
| `LLM_PROVIDER`   | `openai-compatible`  | `openai-compatible`, `anthropic`, `gemini`, `ollama` |
| `LLM_MODEL`      | `gpt-4o-mini`        | Provider model id                       |
| `LLM_BASE_URL`   | provider default     | Override endpoint (e.g. local Ollama)   |
| `LLM_TIMEOUT_SECONDS` | `10.0`          | Bounded request timeout                 |

Keys are never logged; errors are redacted and surfaced clearly. The core
scorer does not require any provider.

## Security

- Demo auth is bound to `127.0.0.1`/`localhost` and refused in production.
- All data API endpoints enforce role-based access (`viewer`/`analyst`/`admin`
  hierarchy); writes additionally require CSRF validation on the session cookie.
- No credentials or private URLs are committed. See `.env.example`.

## API reference

| Method | Path                      | Auth     | Description                          |
|--------|---------------------------|----------|--------------------------------------|
| POST   | `/auth/demo`              | none     | Demo login (localhost only)          |
| POST   | `/auth/logout`            | session  | Clear session                        |
| GET    | `/auth/me`                | session  | Current user                         |
| GET    | `/health`                 | none     | Health                               |
| GET    | `/version`                | none     | Version                              |
| GET    | `/api/postings`           | viewer+  | List, filter by status, paginate     |
| POST   | `/api/postings`           | analyst+ | Import one posting                   |
| POST   | `/api/postings/import`    | analyst+ | Bulk import                          |
| GET    | `/api/postings/{id}`      | viewer+  | Detail                               |
| PATCH  | `/api/postings/{id}`      | analyst+ | Update fields/status                 |
| DELETE | `/api/postings/{id}`      | admin    | Delete                               |
| POST   | `/api/postings/{id}/fetch`| analyst+ | Manual re-fetch (re-queues failures) |
| POST   | `/api/scoring/run`        | analyst+ | Sweep expired + score candidates     |
| POST   | `/api/scoring/sweep`      | analyst+ | Retire past-deadline → `expired`     |
| GET    | `/api/scoring/evaluate`   | analyst+ | IR metrics on labeled fixture        |
| GET    | `/api/scoring/runs/{id}`  | viewer+  | A recorded scoring run               |
| POST   | `/api/scoring/explain`    | analyst+ | Opt-in LLM explanation (needs key)   |

## License

MIT — copyright Alan Vo <alanvo@gmail.com>