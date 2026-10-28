# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

auth-oidc

## Roadmap

### posting-pipeline — Posting import, relevance scoring and lifecycle tracking

Status: done

Acceptance:
- POST /api/postings imports a posting with status 'new'
- POST /api/scoring/run scores all 'new' and retryable 'fetch_failed' postings
- A posting whose fetch fails is marked fetch_failed with an incremented retry count, not expired
- A posting whose fetch succeeds is marked scored with a 0-1 relevance score
- A posting whose deadline passed is marked expired (terminal)
- fetch_failed entries with retry_count below the cap are re-selected as candidates
- GET /api/postings lists postings with filtering by status and pagination
- GET /api/postings/{id} shows full detail including scores and fetch metadata

Implementation: `backend/app/models/orm.py`, `backend/app/models/schemas.py`, `backend/app/services/lifecycle.py`, `backend/app/services/scorer.py`, `backend/app/api/postings.py`, `backend/app/api/scoring.py`

Tests: `backend/tests/test_scorer.py`, `backend/tests/test_lifecycle.py`, `backend/tests/test_postings_api.py`, `backend/tests/test_scoring_api.py`

### scoring-eval — Scorer evaluation against labeled dataset

Status: done

Acceptance:
- GET /api/scoring/evaluate returns metrics computed from a labeled fixture
- Metrics include Precision@k, MAP, and NDCG
- Results are reproducible (deterministic algorithm)

Implementation: `backend/app/services/scorer.py`, `data/labeled_postings.json`

Tests: `backend/tests/test_scorer.py`, `backend/tests/test_scoring_api.py`

### llm-explanation — Opt-in LLM explanations for scoring

Status: done

Acceptance:
- POST /api/scoring/explain generates a grounded, labeled advisory explanation
- Provider errors are surfaced clearly, never fabricated success

Implementation: `backend/app/services/llm.py`, `backend/app/api/scoring.py`

Tests: `backend/tests/test_scoring_api.py`

### auth-oidc — OIDC authorization-code login via Keycloak with SAML brokering

Status: in_progress

Acceptance:
- Demo mode login works on localhost only, refuses in production
- role-based authorization on all data endpoints
- unauthenticated requests rejected, role denial enforced
- OIDC callback validates state, nonce, PKCE and token claims

Implementation: `backend/app/core/security.py`, `backend/app/core/oidc.py`, `backend/app/core/config.py`, `backend/app/api/auth.py`, `keycloak/realm-export.json`, `compose.yaml`

Tests: `backend/tests/test_auth.py`

### application-tracking — Application outcome tracking

Status: planned

Acceptance:
- POST /api/applications records an application against a posting
- PATCH /api/applications/{id} updates the outcome
- GET /api/applications lists applications with filtering

Implementation: `backend/app/models/orm.py`, `backend/app/api/applications.py`

Tests: `backend/tests/test_applications.py`

### cv-tailor — CV/resume tailoring to a posting

Status: planned

Acceptance:
- POST /api/cv/tailor analyzes a posting against a base CV and returns keyword gaps
- Opt-in LLM enhancement generates natural-language bullets

Implementation: `backend/app/services/cv_tailor.py`, `backend/app/api/cv.py`

Tests: `backend/tests/test_cv_tailor.py`

