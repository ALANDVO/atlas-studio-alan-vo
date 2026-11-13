# Changelog

## 1.4.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.4.0 — application-tracking feature

### Added

- Application tracking API (`backend/app/api/applications.py`): POST/GET/PATCH/DELETE `/api/applications` with stage management (applied, screening, interview, offer, rejected, withdrawn)
- `Application` ORM model (`backend/app/models/orm.py`) with posting_id foreign key, stage, notes, applied_at, updated_at
- Application schemas (`backend/app/models/schemas.py`): ApplicationCreate, ApplicationUpdate, ApplicationRead, ApplicationPage
- 11 new integration tests (`backend/tests/test_applications.py`) covering create, get, list, filter by stage, update, delete, auth
- All 104 backend tests pass

## 1.3.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.2.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

### Fixed

- Fixed duplicate stopwords in TF-IDF scorer (`backend/app/services/scorer.py`): removed duplicate "may" and "than" entries
- Added edge-case tests for tokenization and scoring (`backend/tests/test_scorer.py`):
  - `test_short_text_becomes_empty`: handles very short texts that tokenize to empty
  - `test_stopwords_only_text_scores_zero`: verifies stopwords-only text scores 0.0
- All 93 backend tests pass

## 1.1.0 — 2026-11-05

### Added

- Test for demo mode production refusal (auth-oidc feature completion)

### Changed

- auth-oidc feature marked complete: OIDC authorization-code flow with PKCE for Keycloak, demo mode (localhost-only), and role-based authorization
- All 91 backend tests pass


## 1.1.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.0.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-17

### Added

- FastAPI backend with async SQLAlchemy, UUID-based models, and CORS support.
- Pydantic settings management with environment-driven configuration.
- Demo login (localhost-only) with HttpOnly SameSite cookies and CSRF token protection.
- Role-based access control: viewer, analyst, admin.
- Job-posting CRUD API: import, list, get, update, delete, and manual re-fetch.
- Deterministic TF-IDF cosine-similarity scorer with tokenization, IDF, and normalized [0, 1] scores.
- Scorer evaluation with IR metrics: precision@k, recall@k, MAP, NDCG@k.
- Posting lifecycle with correct `fetch_failed` (retryable) vs `expired` (terminal) semantics per issue #534.
- Opt-in LLM explanation advisor with httpx adapters for OpenAI-compatible, Anthropic, Gemini, and Ollama providers.
- React/Vite frontend with dark theme, responsive layout, and full type safety.
- Typed API client using native fetch with cookie-based auth and CSRF header support.
- Component tests (Vitest + Testing Library) covering StatusBadge, PostingsDashboard, and ImportDialog.
- Backend tests (pytest + pytest-asyncio) covering scorer, lifecycle, auth, postings API, and scoring API.
- Docker support: backend and frontend multi-stage, non-root images.
- Docker Compose with Keycloak and Caddy TLS profiles.
### Changed

- Added OIDC authorization-code flow with PKCE (feature: auth-oidc).
- New endpoints: `GET /auth/oidc/login` to initiate login, `GET /auth/oidc/callback` to handle Keycloak redirect.
- Added OIDC configuration settings: `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`, `OIDC_SCOPES`.
- Added `python-jose` and `authlib` dependencies for JWT validation and OAuth2 client.
- Added tests for OIDC login initiation and callback validation (state, nonce, PKCE, token claims).

### Fixed

- Posting lifecycle sweep is invoked at the start of a scoring round (issue #534), so past-deadline postings are retired to `expired` rather than scored. The `POST /api/scoring/run` response and the recorded `ScoringRun` now report the real expired count instead of a hardcoded 0.
- Added explicit `POST /api/scoring/sweep` endpoint for retiring past-deadline postings; unauthenticated access is rejected.

---

Alan Vo · [alanvo.net](https://alanvo.net) · [X: @alanvoasi](https://x.com/alanvoasi)
