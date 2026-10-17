"""Authentication endpoints.

Demo mode: ``POST /auth/demo`` issues an HttpOnly session cookie valid only
on localhost and only when ``AUTH_DEMO_MODE=true`` and the env is non-production.

Full OIDC authorization-code login via Keycloak is a planned milestone
(feature: auth-oidc).  See docs/auth.md.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..core.config import settings
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