"""Authentication, authorization, and CSRF for Atlas Studio.

Architecture: backend-managed sessions with HttpOnly SameSite cookies and
CSRF protection on cookie-authenticated writes (contract choice A).

Demo mode: a local-only mock login for development.  When
``AUTH_DEMO_MODE=true`` and the process is on localhost, ``POST /auth/demo``
issues a session.  In production (PRODUCTION=true / environment=production)
demo mode startup is refused.

Full OIDC/Keycloak authorization-code login is a planned milestone
(feature: auth-oidc).  See docs/auth.md for the planned SAML brokering flow.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

COOKIE_NAME = "atlas_session"
CSRF_HEADER = "x-csrf-token"


class Role(str, Enum):
    viewer = "viewer"
    analyst = "analyst"
    admin = "admin"

    @classmethod
    def hierarchy(cls) -> list["Role"]:
        """Ordered from least to most privileged."""
        return [cls.viewer, cls.analyst, cls.admin]

    def level(self) -> int:
        return Role.hierarchy().index(self)

    def implies(self, other: "Role") -> bool:
        return self.level() >= other.level()


class CurrentUser:
    """Authenticated user principal carried through the request."""

    def __init__(self, sub: str, role: Role, name: str = "demo user"):
        self.sub = sub
        self.role = role
        self.name = name

    def can(self, required: Role) -> bool:
        """True if this user's role satisfies *required* or higher."""
        return self.role.implies(required)

    def dict(self) -> dict[str, str]:
        return {"sub": self.sub, "role": self.role.value, "name": self.name}


# ---------------------------------------------------------------------------
# Session helpers (opaque token stored in HttpOnly cookie)
# ---------------------------------------------------------------------------
_SESSIONS: dict[str, CurrentUser] = {}


def create_session(sub: str, role: Role, name: str = "demo user") -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = CurrentUser(sub, role, name)
    return token


def revoke_session(token: str) -> None:
    _SESSIONS.pop(token, None)


def get_session_user(token: str | None) -> CurrentUser | None:
    if not token:
        return None
    return _SESSIONS.get(token)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)


def _extract_cookie_token(request: Request) -> str | None:
    return request.cookies.get(COOKIE_NAME)


def _token_from_request(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None,
) -> str | None:
    """Cookie takes priority; Authorization header as fallback for API clients."""
    token = _extract_cookie_token(request)
    if token:
        return token
    if bearer and bearer.scheme.lower() == "bearer":
        return bearer.credentials
    return None


async def get_current_user(
    request: Request,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> CurrentUser:
    token = _token_from_request(request, bearer)
    user = get_session_user(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return user


def require_role(role: Role):
    """Dependency factory enforcing a minimum role."""

    def _dependency(
        user: Annotated[CurrentUser, Depends(get_current_user)],
        request: Request,
    ) -> CurrentUser:
        if not user.can(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' lacks '{role.value}' privilege",
            )
        # Validate CSRF for state-changing requests when using cookie auth.
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and _extract_cookie_token(request):
            _validate_csrf(request)
        return user

    return _dependency


def _validate_csrf(request: Request) -> None:
    """Validate CSRF token on cookie-authenticated writes."""
    cookie_token = _extract_cookie_token(request)
    csrf_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")
    # Constant-time comparison
    if not secrets.compare_digest(cookie_token, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")


def generate_csrf_token(session_token: str) -> str:
    """CSRF token is the session token itself (opaque, unguessable)."""
    return session_token


def is_demo_mode_allowed() -> bool:
    """Demo mode is only available on localhost in a non-production env."""
    if settings.is_production:
        return False
    host = settings.host
    return host in ("127.0.0.1", "localhost", "::1")


def audit_entry(user: CurrentUser, action: str, resource: str, detail: str = "") -> dict:
    """Build an audit-log record."""
    return {
        "user_id": user.sub,
        "action": action,
        "resource": resource,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }