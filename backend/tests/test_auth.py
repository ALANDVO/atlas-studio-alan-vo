"""Tests for authentication: demo mode, roles, CSRF, unauthenticated rejection."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestDemoLogin:
    async def test_demo_login_success(self, client):
        resp = await client.post("/auth/demo?role=analyst")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == "analyst"
        assert "csrf_token" in data

    async def test_demo_login_default_role(self, client):
        resp = await client.post("/auth/demo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == "viewer"

    async def test_demo_login_invalid_role(self, client):
        resp = await client.post("/auth/demo?role=superadmin")
        assert resp.status_code == 400

    async def test_roles_list(self, client):
        resp = await client.get("/auth/roles")
        assert resp.status_code == 200
        roles = resp.json()
        assert "viewer" in roles
        assert "analyst" in roles
        assert "admin" in roles


class TestUnauthenticatedRejection:
    async def test_get_postings_unauthenticated(self, client):
        resp = await client.get("/api/postings")
        assert resp.status_code == 401

    async def test_post_posting_unauthenticated(self, client):
        resp = await client.post("/api/postings", json={
            "source": "https://example.com", "company": "X", "title": "Y",
        })
        assert resp.status_code == 401

    async def test_get_scoring_run_unauthenticated(self, client):
        resp = await client.get("/api/scoring/runs/nonexistent")
        assert resp.status_code == 401


class TestRoleDenial:
    async def test_viewer_cannot_create(self, viewer_client):
        resp = await viewer_client.post("/api/postings", json={
            "source": "https://example.com", "company": "X", "title": "Y",
        })
        assert resp.status_code == 403

    async def test_viewer_cannot_delete(self, viewer_client):
        resp = await viewer_client.delete("/api/postings/nonexistent")
        assert resp.status_code == 403  # role denial, viewer cannot delete

    async def test_analyst_can_create(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json={
            "source": "https://example.com/job/1",
            "company": "TestCorp",
            "title": "Machine Learning Engineer",
            "location": "Remote",
            "raw_snippet": "ML engineer role with TensorFlow and PyTorch.",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "new"


class TestCSFSProtection:
    async def test_csrf_missing_rejected(self, client):
        # Login (cookie is set) but don't send CSRF header for a write.
        resp = await client.post("/auth/demo?role=analyst")
        assert resp.status_code == 200
        # Client has the cookie but no CSRF header → 403
        resp = await client.post("/api/postings", json={
            "source": "https://example.com", "company": "X", "title": "Y",
        })
        assert resp.status_code == 403

    async def test_csrf_mismatch_rejected(self, client):
        resp = await client.post("/auth/demo?role=analyst")
        assert resp.status_code == 200
        # Send wrong CSRF token
        resp = await client.post("/api/postings", json={
            "source": "https://example.com", "company": "X", "title": "Y",
        }, headers={"x-csrf-token": "wrong-token"})
        assert resp.status_code == 403

    async def test_csrf_correct_accepted(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json={
            "source": "https://example.com/job/1",
            "company": "TestCorp",
            "title": "ML Engineer",
            "raw_snippet": "machine learning tensorflow pytorch python model",
        })
        assert resp.status_code == 201


class TestLogout:
    async def test_logout_clears_session(self, analyst_client):
        resp = await analyst_client.post("/auth/logout")
        assert resp.status_code == 200
        # After logout, requests should be unauthenticated
        resp = await analyst_client.get("/auth/me")
        assert resp.status_code == 401
        # Clear CSRF header for the unauthenticated request
        analyst_client.headers.pop("x-csrf-token", None)

    async def test_current_user(self, analyst_client):
        resp = await analyst_client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "analyst"


class TestRoleHierarchy:
    async def test_admin_implies_analyst(self, admin_client):
        # Admin can create (requires analyst)
        resp = await admin_client.post("/api/postings", json={
            "source": "https://example.com", "company": "X", "title": "Y",
            "raw_snippet": "some snippet text here",
        })
        assert resp.status_code == 201

    async def test_analyst_cannot_delete(self, analyst_client):
        # Create then try to delete as analyst (requires admin)
        resp = await analyst_client.post("/api/postings", json={
            "source": "https://example.com", "company": "X", "title": "Y",
            "raw_snippet": "some snippet text here",
        })
        assert resp.status_code == 201
        posting_id = resp.json()["id"]
        resp = await analyst_client.delete(f"/api/postings/{posting_id}")
        assert resp.status_code == 403