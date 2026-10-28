"""Application configuration.

All secrets come from environment variables or .env.  No credential
literals are ever committed.
"""
from __future__ import annotations

import os
from functools import cached_property
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration sourced from the environment."""

    model_config = {"env_file": ".env", "extra": "ignore"}

    # --- Identity -----------------------------------------------------------
    app_name: str = "Atlas Studio"
    version: str = Field(default_factory=lambda: _read_version())
    environment: str = Field(default="development")

    # --- Auth ---------------------------------------------------------------
    # Demo mode provides a local-only mock login for development.  It must
    # NEVER be available in production.
    auth_demo_mode: bool = Field(default=False, validation_alias="AUTH_DEMO_MODE")
    auth_demo_roles: str = Field(
        default="viewer,analyst,admin",
        validation_alias="AUTH_DEMO_ROLES",
    )
    secret_key: str = Field(default="dev-insecure-key-change-me")

    # --- Database ----------------------------------------------------------
    database_url: str = Field(
        default="sqlite+aiosqlite:///./atlas_studio.db",
        validation_alias="DATABASE_URL",
    )

    # --- LLM (optional, opt-in) ---------------------------------------------
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    llm_provider: str = Field(default="openai-compatible", validation_alias="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="LLM_MODEL")
    llm_base_url: str | None = Field(default=None, validation_alias="LLM_BASE_URL")
    # --- OIDC (Keycloak) ----------------------------------------------------
    oidc_issuer_url: str | None = Field(default=None, validation_alias="OIDC_ISSUER_URL")
    oidc_client_id: str | None = Field(default=None, validation_alias="OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(default=None, validation_alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str | None = Field(default=None, validation_alias="OIDC_REDIRECT_URI")
    oidc_scopes: str = Field(default="openid profile email roles", validation_alias="OIDC_SCOPES")


    # --- Server ------------------------------------------------------------
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)

    @field_validator("secret_key")
    @classmethod
    def _secret_key_not_empty(cls, v: str) -> str:
        if not v or len(v) < 8:
            raise ValueError("secret_key must be at least 8 characters")
        return v

    @property
    def is_production(self) -> bool:
        """True when the deployment targets production (refuses demo mode)."""
        return self.environment.lower() in ("production", "prod")

    @property
    def demo_roles_list(self) -> list[str]:
        return [r.strip() for r in self.auth_demo_roles.split(",") if r.strip()]

    @cached_property
    def bind_address(self) -> str:
        """Host binding — always 127.0.0.1 in development."""
        if self.is_production:
            return "0.0.0.0"
        return "127.0.0.1"

def _read_version() -> str:
    """Read the canonical version from the VERSION file."""
    version_file = Path(__file__).resolve().parent.parent.parent.parent / "VERSION"
    try:
        return version_file.read_text().strip()
    except FileNotFoundError:
        return "0.0.0"


settings = Settings()