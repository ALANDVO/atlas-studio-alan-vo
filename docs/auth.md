# Authentication & Authorization

Atlas Studio supports two authentication modes. The current implementation uses
**local demo auth**; full OIDC is a planned milestone.

## Demo mode (current, localhost only)

Enabled by setting `AUTH_DEMO_MODE=true` (see `.env.example`). On startup the
app validates:

- If `ENVIRONMENT=production`, demo mode is **refused** — the app will not
  start. Set `ENVIRONMENT=development` (or `HOST=127.0.0.1`) for local work.
- The binding address is restricted to `127.0.0.1` / `localhost` / `::1`.

Demo login issues an opaque session token stored in an `atlas_session`
**HttpOnly `SameSite=Lax`** cookie. A CSRF token (equal to the session token)
is returned in the login body and must be sent as the `x-csrf-token` header on
write requests (POST/PATCH/DELETE). The `/auth/me` and `/auth/roles` endpoints
are unauthenticated/read-only.

### Roles

| Role    | Level | Can                                  |
|---------|-------|--------------------------------------|
| `viewer`| 10    | read postings, scoring runs          |
| `analyst`| 20   | import, score, fetch, explain        |
| `admin` | 30    | delete postings (implies analyst)    |

Authorization is enforced on **all** data endpoints via the `require_role`
dependency. Unauthenticated requests are rejected with `401`; insufficient-role
requests with `403`.

### Demo login

```bash
curl -c cookies.txt -X POST "http://127.0.0.1:8000/auth/demo?role=analyst"
# -> { "user": {...}, "csrf_token": "<token>" }

# Authenticated read
curl -b cookies.txt "http://127.0.0.1:8000/api/postings"

# Authenticated write (CSRF token required)
curl -b cookies.txt -H "x-csrf-token: <token>" \
  -X POST "http://127.0.0.1:8000/api/postings" -d @posting.json
```

## OIDC login via Keycloak (planned milestone)

The production target is OpenID Connect authorization-code login through
Keycloak, with SAML Identity Provider brokering. `compose.yaml` includes a
Keycloak service behind the `auth` profile and a realm import
(`keycloak/realm-export.json`). The backend OIDC callback, discovery,
state+nonce+PKCE validation, and token signature/issuer/audience checks are
tracked as the `auth-oidc` feature and are **not yet wired**. Until then,
production deployments should keep `AUTH_DEMO_MODE=false` and front the API
behind an operator-managed identity proxy, or complete the OIDC milestone.

### Keycloak realm (reference only)

The shipped `keycloak/realm-export.json` defines the `atlas-studio` realm with
`viewer`, `analyst`, and `admin` client roles and SAML identity-provider
brokering slots. To enable:

1. Set `KEYCLOAK_URL`, `KEYCLOAK_CLIENT_ID`, and `KEYCLOAK_CLIENT_SECRET`.
2. Configure SAML IdP enrollment in the Keycloak admin console under
   _Identity providers_.
3. Start with `docker compose --profile auth up --build`.