"""FastAPI application factory for Atlas Studio.

Run locally:
    PYTHONPATH=backend python -m app.main
    # or: .venv/bin/uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

Docker uses the same entrypoint:
    CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
"""
from __future__ import annotations

import datetime as _dt
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.auth import router as auth_router
from .api.postings import router as postings_router
from .api.scoring import router as scoring_router
from .core.config import settings
from .core.database import init_db

VERSION = (Path(__file__).resolve().parent.parent.parent / "VERSION").read_text().strip()


def create_app() -> FastAPI:
    """Application factory — same entrypoint for Docker and local."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Refuse demo mode in production.
        if settings.is_production and settings.auth_demo_mode:
            raise RuntimeError(
                "Demo mode is refused in production. "
                "Disable AUTH_DEMO_MODE or set environment to development."
            )
        await init_db()
        yield

    app = FastAPI(
        title="Atlas Studio",
        description=(
            "Local AI job application framework. Evaluate postings, score "
            "relevance against a target role, track the lifecycle with correct "
            "fetch-failure handling."
        ),
        version=VERSION,
        lifespan=lifespan,
    )

    # CORS — bind to configured origins (default: localhost dev).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(postings_router)
    app.include_router(scoring_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "atlas-studio", "version": VERSION}

    @app.get("/version")
    async def version() -> dict[str, str]:
        return {"version": VERSION, "environment": settings.environment}

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": "Atlas Studio",
            "version": VERSION,
            "docs": "/docs",
        }

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=settings.bind_address,
        port=settings.port,
    )