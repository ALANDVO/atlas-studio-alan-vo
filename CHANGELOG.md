# Changelog

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
- GitHub Actions CI: backend tests, frontend build+test, Docker image builds.

### Fixed

- Posting lifecycle sweep is invoked at the start of a scoring round (issue #534), so past-deadline postings are retired to `expired` rather than scored. The `POST /api/scoring/run` response and the recorded `ScoringRun` now report the real expired count instead of a hardcoded 0.
- Added explicit `POST /api/scoring/sweep` endpoint for retiring past-deadline postings; unauthenticated access is rejected.