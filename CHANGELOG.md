# Changelog

## 1.6.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

\## 1.5.1 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.4.0 — work-in-progress checkpoint

### Added

- CV/resume tailoring API (`backend/app/api/cv.py`): POST /api/cv/tailor analyzes a posting against a base CV and returns keyword gaps
- CV tailoring service (`backend/app/services/cv_tailor.py`): deterministic token-based keyword gap analysis
- 3 integration tests (`backend/tests/test_cv_tailor.py`) covering basic gaps, no-gaps edge case, and empty CV

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

---

Alan Vo · [alanvo.net](https://alanvo.net) · [X: @alanvoasi](https://x.com/alanvoasi)
