"""OIDC (Keycloak) integration for Atlas Studio.

Provides authorization-code flow with PKCE, state, nonce validation,
and JWT token verification against the OIDC issuer's JWKS.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import jwt, JWTError
from jose.utils import base64url_decode

from .config import settings


# In-memory storage for PKCE verifiers and state/nonces (use Redis in production)
_PKCE_VERIFIERS: dict[str, str] = {}
_OIDC_STATES: dict[str, dict] = {}  # state -> {nonce, pkce_verifier, redirect_uri, created_at}


def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge_b64 = (
        __import__("base64").urlsafe_b64encode(code_challenge).decode().rstrip("=")
    )
    return code_verifier, code_challenge_b64


def store_pkce_verifier(state: str, code_verifier: str) -> None:
    """Store PKCE verifier associated with state."""
    _PKCE_VERIFIERS[state] = code_verifier


def consume_pkce_verifier(state: str) -> str | None:
    """Retrieve and remove PKCE verifier for state."""
    return _PKCE_VERIFIERS.pop(state, None)


def store_oidc_state(state: str, nonce: str, code_verifier: str, redirect_uri: str) -> None:
    """Store OIDC state with associated nonce and PKCE verifier."""
    _OIDC_STATES[state] = {
        "nonce": nonce,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "created_at": time.time(),
    }


def consume_oidc_state(state: str) -> dict | None:
    """Retrieve and remove OIDC state, validating it hasn't expired (10 min)."""
    data = _OIDC_STATES.pop(state, None)
    if data and time.time() - data["created_at"] < 600:
        return data
    return None


@dataclass
class OIDCConfig:
    """Resolved OIDC configuration from issuer discovery."""
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str | None = None
    end_session_endpoint: str | None = None


_OIDC_CONFIG_CACHE: OIDCConfig | None = None
_JWKS_CACHE: dict | None = None
_JWKS_FETCHED_AT: float = 0


async def discover_oidc_config() -> OIDCConfig:
    """Fetch OIDC provider configuration from issuer's well-known endpoint."""
    global _OIDC_CONFIG_CACHE
    if _OIDC_CONFIG_CACHE:
        return _OIDC_CONFIG_CACHE

    if not settings.oidc_issuer_url:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC not configured: OIDC_ISSUER_URL not set",
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration"
        )
        resp.raise_for_status()
        data = resp.json()

    _OIDC_CONFIG_CACHE = OIDCConfig(
        issuer=data["issuer"],
        authorization_endpoint=data["authorization_endpoint"],
        token_endpoint=data["token_endpoint"],
        jwks_uri=data["jwks_uri"],
        userinfo_endpoint=data.get("userinfo_endpoint"),
        end_session_endpoint=data.get("end_session_endpoint"),
    )
    return _OIDC_CONFIG_CACHE


async def fetch_jwks() -> dict:
    """Fetch and cache JWKS from the OIDC provider."""
    global _JWKS_CACHE, _JWKS_FETCHED_AT
    # Cache for 1 hour
    if _JWKS_CACHE and time.time() - _JWKS_FETCHED_AT < 3600:
        return _JWKS_CACHE

    config = await discover_oidc_config()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(config.jwks_uri)
        resp.raise_for_status()
        _JWKS_CACHE = resp.json()
        _JWKS_FETCHED_AT = time.time()
        return _JWKS_CACHE


def get_signing_key(jwks: dict, kid: str) -> dict | None:
    """Extract signing key from JWKS by key ID."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def validate_id_token(id_token: str, nonce: str | None = None) -> dict:
    """Validate ID token signature, issuer, audience, expiry, and nonce."""
    config = await discover_oidc_config()
    jwks = await fetch_jwks()

    # Decode header to get key ID
    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid ID token header: {e}",
        )

    kid = header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ID token missing key ID (kid)",
        )

    signing_key = get_signing_key(jwks, kid)
    if not signing_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signing key not found in JWKS",
        )

    # Validate and decode the token
    try:
        # Convert JWK to PEM format for python-jose
        from jose.utils import RSAKey
        key = RSAKey(key=signing_key, algorithm=header.get("alg", "RS256"))

        claims = jwt.decode(
            id_token,
            key,
            algorithms=[header.get("alg", "RS256")],
            audience=settings.oidc_client_id,
            issuer=config.issuer,
            options={"verify_aud": True, "verify_iss": True, "verify_exp": True},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"ID token validation failed: {e}",
        )

    # Validate nonce if provided
    if nonce and claims.get("nonce") != nonce:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ID token nonce mismatch",
        )

    return claims


def build_authorization_url(
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
) -> str:
    """Build the OIDC authorization URL with PKCE."""
    if not settings.oidc_issuer_url:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC not configured",
        )

    # Use the issuer URL as base; the actual endpoints come from discovery
    base = settings.oidc_issuer_url.rstrip("/")
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": redirect_uri,
        "scope": settings.oidc_scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{base}/protocol/openid-connect/auth?{urlencode(params)}"


async def build_authorization_url_async(
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
) -> str:
    """Build the OIDC authorization URL with PKCE (async, uses discovery)."""
    config = await discover_oidc_config()
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": redirect_uri,
        "scope": settings.oidc_scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{config.authorization_endpoint}?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> dict:
    """Exchange authorization code for tokens at the token endpoint."""
    config = await discover_oidc_config()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            config.token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "code_verifier": code_verifier,
            },
            headers={"Accept": "application/json"},
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token exchange failed: {resp.text}",
            )
        return resp.json()


def map_keycloak_roles_to_role(claims: dict) -> "Role":
    """Map Keycloak realm/client roles to our Role enum."""
    from .security import Role

    # Keycloak puts realm roles in `realm_access.roles` and client roles in
    # `resource_access.<client_id>.roles`
    realm_roles = claims.get("realm_access", {}).get("roles", [])
    client_roles = claims.get("resource_access", {}).get(settings.oidc_client_id or "", {}).get("roles", [])

    all_roles = set(realm_roles) | set(client_roles)

    if "admin" in all_roles:
        return Role.admin
    if "analyst" in all_roles:
        return Role.analyst
    return Role.viewer


def create_user_from_claims(claims: dict) -> tuple[str, "Role", str]:
    """Create user identity from validated ID token claims.

    Returns (sub, role, name).
    """
    from .security import Role

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ID token missing subject (sub)",
        )

    name = claims.get("name") or claims.get("preferred_username") or claims.get("email") or "OIDC user"
    role = map_keycloak_roles_to_role(claims)

    return sub, role, name
