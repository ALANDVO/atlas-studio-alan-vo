"""Authentication endpoints.

Demo mode: ``POST /auth/demo`` issues an HttpOnly session cookie valid only
on localhost and only when ``AUTH_DEMO_MODE=true`` and the env is non-production.

Full OIDC authorization-code login via Keycloak is a planned milestone
(feature: auth-oidc).  See docs/auth.md.
"""
from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..core.config import settings
from ..core.oidc import (
    build_authorization_url_async,
    consume_oidc_state,
    create_user_from_claims,
    exchange_code_for_tokens,
    generate_pkce_pair,
    store_oidc_state,
    validate_id_token,
)
from ..core.security import (
    COOKIE_NAME,
    CurrentUser,
    Role,
    create_session,
    generate_csrf_token,
    get_current_user,
    is_demo_mode_allowed,
    revoke_session,
)
from ..models.schemas import LoginResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/oidc/login")
async def oidc_login(
    request: Request,
    redirect_uri: str | None = None,
) -> dict[str, str]:
    """Initiate OIDC authorization-code flow with PKCE.

    Returns the authorization URL to redirect the user to. The frontend should
    redirect the browser to this URL.
    """
    if not settings.oidc_issuer_url or not settings.oidc_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC not configured. Set OIDC_ISSUER_URL and OIDC_CLIENT_ID.",
        )

    # Generate PKCE pair and state/nonce
    code_verifier, code_challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    # Use provided redirect_uri or default from config
    oidc_redirect_uri = redirect_uri or settings.oidc_redirect_uri
    if not oidc_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC redirect_uri not configured. Set OIDC_REDIRECT_URI or pass redirect_uri query param.",
        )

    # Store state with PKCE verifier and nonce
    store_oidc_state(state, nonce, code_verifier, oidc_redirect_uri)

    # Build authorization URL
    auth_url = await build_authorization_url_async(
        redirect_uri=oidc_redirect_uri,
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
    )

    return {"authorization_url": auth_url, "state": state}


@router.get("/oidc/callback")
async def oidc_callback(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> LoginResponse:
    """Handle OIDC authorization-code callback.

    Validates state, nonce, PKCE, and ID token claims. Issues a session cookie
    on success.
    """
    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OIDC error: {error} - {error_description or ''}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code or state parameter",
        )

    # Consume and validate state
    oidc_state = consume_oidc_state(state)
    if not oidc_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    nonce = oidc_state["nonce"]
    code_verifier = oidc_state["code_verifier"]
    redirect_uri = oidc_state["redirect_uri"]

    # Exchange code for tokens
    tokens = await exchange_code_for_tokens(code, code_verifier, redirect_uri)

    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token response missing ID token",
        )

    # Validate ID token (signature, issuer, audience, expiry, nonce)
    claims = await validate_id_token(id_token, nonce)

    # Create user from claims
    sub, role, name = create_user_from_claims(claims)

    # Create session
    session_token = create_session(sub=sub, role=role, name=name)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        max_age=8 * 3600,
        httponly=True,
        samesite="lax",
        secure=False,  # False for localhost dev; set True behind TLS in prod
        path="/",
    )
    csrf = generate_csrf_token(session_token)
    return LoginResponse(
        user={"sub": sub, "role": role.value, "name": name},
        csrf_token=csrf,
    )


@router.post("/demo", response_model=LoginResponse)
async def demo_login(
    request: Request,
    response: Response,
    role: str | None = None,
) -> LoginResponse:
    """Local-only demo login.

    Refuses to start demo mode in production.  The role query param selects
    among the configured demo roles (viewer, analyst, admin).
    """
    if not settings.auth_demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode is not enabled. Set AUTH_DEMO_MODE=true.",
        )
    if settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode is refused in production.",
        )
    if not is_demo_mode_allowed():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode is only available on localhost.",
        )

    available_roles = settings.demo_roles_list
    if role and role not in available_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown role '{role}'. Available: {', '.join(available_roles)}",
        )
    chosen = role if role else "viewer"

    try:
        user_role = Role(chosen)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {role}"
        )

    session_token = create_session(
        sub=f"demo-{chosen}", role=user_role, name=f"Demo {chosen}"
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        max_age=8 * 3600,
        httponly=True,
        samesite="lax",
        secure=False,  # False for localhost dev; set True behind TLS in prod
        path="/",
    )
    csrf = generate_csrf_token(session_token)
    return LoginResponse(
        user={"sub": f"demo-{chosen}", "role": chosen, "name": f"Demo {chosen}"},
        csrf_token=csrf,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, str]:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        revoke_session(token)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"status": "logged out"}


@router.get("/me", response_model=UserRead)
async def read_current_user(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> UserRead:
    return UserRead(sub=user.sub, role=user.role.value, name=user.name)


@router.get("/roles", response_model=list[str])
async def list_roles() -> list[str]:
    """List available roles (read-only, no auth required)."""
    return [r.value for r in Role]
