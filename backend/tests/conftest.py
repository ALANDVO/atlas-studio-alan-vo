"""Shared pytest fixtures for Atlas Studio backend tests."""
from __future__ import annotations

import asyncio
import os
import sys

# Ensure backend/ is importable.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Set test environment BEFORE importing app modules.
os.environ["AUTH_DEMO_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_atlas.db"
os.environ["SECRET_KEY"] = "test-secret-key-123456789"
os.environ["ENVIRONMENT"] = "development"
os.environ["HOST"] = "127.0.0.1"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.database import AsyncSessionFactory, engine, init_db
from app.core.security import _SESSIONS
from app.models.orm import AuditLog, LabelingExample, Posting, ScoringRun

ALL_MODELS = [AuditLog, ScoringRun, LabelingExample, Posting]


@pytest.fixture(scope="session", autouse=True)
async def db_setup():
    """Create tables once for the test session."""
    await init_db()
    yield
    await engine.dispose()
    test_db = os.path.join(os.path.dirname(_BACKEND_DIR), "test_atlas.db")
    if os.path.exists("test_atlas.db"):
        os.remove("test_atlas.db")
    if os.path.exists(test_db):
        os.remove(test_db)


@pytest.fixture(autouse=True)
async def clean_db():
    """Clean all tables and sessions before each test."""
    _SESSIONS.clear()
    async with AsyncSessionFactory() as session:
        for model in ALL_MODELS:
            await session.execute(text(f"DELETE FROM {model.__tablename__}"))
        await session.commit()


@pytest.fixture
async def client():
    """FastAPI test client (unauthenticated)."""
    from app.main import create_app

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac


@pytest.fixture
async def analyst_client(client):
    """Client authenticated as analyst (with CSRF token)."""
    resp = await client.post("/auth/demo?role=analyst")
    assert resp.status_code == 200, resp.text
    csrf = resp.json()["csrf_token"]
    client.headers["x-csrf-token"] = csrf
    return client


@pytest.fixture
async def admin_client(client):
    """Client authenticated as admin (with CSRF token)."""
    resp = await client.post("/auth/demo?role=admin")
    assert resp.status_code == 200, resp.text
    csrf = resp.json()["csrf_token"]
    client.headers["x-csrf-token"] = csrf
    return client


@pytest.fixture
async def viewer_client(client):
    """Client authenticated as viewer."""
    resp = await client.post("/auth/demo?role=viewer")
    assert resp.status_code == 200, resp.text
    csrf = resp.json()["csrf_token"]
    client.headers["x-csrf-token"] = csrf
    return client