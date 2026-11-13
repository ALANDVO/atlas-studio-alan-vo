"""Integration tests for the applications API — real HTTP boundary, DB-backed."""
from __future__ import annotations

import pytest


def _posting_payload() -> dict:
    return {
        "source": "https://example.com/job/app-test",
        "company": "AppCo",
        "title": "Backend Engineer",
        "location": "Remote",
        "deadline": "2099-12-31",
        "raw_snippet": "Backend engineer with Python and FastAPI experience.",
    }


class TestCreateApplication:
    async def test_create_application(self, analyst_client):
        # First create a posting
        resp = await analyst_client.post("/api/postings/", json=_posting_payload())
        assert resp.status_code == 201, resp.text
        posting = resp.json()

        resp = await analyst_client.post(
            "/api/applications/",
            json={"posting_id": posting["id"], "stage": "applied", "notes": "Initial application"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["stage"] == "applied"
        assert data["notes"] == "Initial application"

    async def test_create_application_invalid_posting(self, analyst_client):
        resp = await analyst_client.post(
            "/api/applications/",
            json={"posting_id": "nonexistent", "stage": "applied"},
        )
        assert resp.status_code == 404

    async def test_create_application_invalid_stage(self, analyst_client):
        resp = await analyst_client.post("/api/postings/", json=_posting_payload())
        posting = resp.json()

        resp = await analyst_client.post(
            "/api/applications/",
            json={"posting_id": posting["id"], "stage": "invalid"},
        )
        assert resp.status_code == 422


class TestGetApplication:
    async def test_get_application(self, analyst_client):
        resp = await analyst_client.post("/api/postings/", json=_posting_payload())
        posting = resp.json()
        resp = await analyst_client.post(
            "/api/applications/",
            json={"posting_id": posting["id"]},
        )
        app = resp.json()

        resp = await analyst_client.get(f"/api/applications/{app['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == app["id"]

    async def test_get_nonexistent(self, analyst_client):
        resp = await analyst_client.get("/api/applications/nonexistent")
        assert resp.status_code == 404


class TestListApplications:
    async def test_list_applications(self, analyst_client):
        # Create posting
        resp = await analyst_client.post("/api/postings/", json=_posting_payload())
        posting = resp.json()

        # Create application
        await analyst_client.post(
            "/api/applications/",
            json={"posting_id": posting["id"]},
        )

        resp = await analyst_client.get("/api/applications/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["page_size"] == 20

    async def test_filter_by_stage(self, analyst_client):
        resp = await analyst_client.post("/api/postings/", json=_posting_payload())
        posting = resp.json()

        await analyst_client.post(
            "/api/applications/",
            json={"posting_id": posting["id"], "stage": "applied"},
        )

        resp = await analyst_client.get("/api/applications/?stage=applied")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = await analyst_client.get("/api/applications/?stage=interview")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestUpdateApplication:
    async def test_update_stage(self, analyst_client):
        resp = await analyst_client.post("/api/postings/", json=_posting_payload())
        posting = resp.json()

        resp = await analyst_client.post(
            "/api/applications/",
            json={"posting_id": posting["id"]},
        )
        app = resp.json()

        resp = await analyst_client.patch(
            f"/api/applications/{app['id']}",
            json={"stage": "interview"},
        )
        assert resp.status_code == 200
        assert resp.json()["stage"] == "interview"

    async def test_update_nonexistent(self, analyst_client):
        resp = await analyst_client.patch(
            "/api/applications/nonexistent",
            json={"stage": "offer"},
        )
        assert resp.status_code == 404


class TestDeleteApplication:
    async def test_delete_application(self, analyst_client):
        resp = await analyst_client.post("/api/postings/", json=_posting_payload())
        posting = resp.json()

        resp = await analyst_client.post(
            "/api/applications/",
            json={"posting_id": posting["id"]},
        )
        app = resp.json()

        resp = await analyst_client.delete(f"/api/applications/{app['id']}")
        assert resp.status_code == 204

        resp = await analyst_client.get(f"/api/applications/{app['id']}")
        assert resp.status_code == 404


class TestAuth:
    async def test_unauthenticated(self, client):
        resp = await client.post("/api/applications/", json={"posting_id": "x"})
        assert resp.status_code == 401
