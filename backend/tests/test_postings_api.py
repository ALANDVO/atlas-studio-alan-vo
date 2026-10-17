"""Integration tests for the postings API — real HTTP boundary, DB-backed."""
from __future__ import annotations

import pytest


SAMPLE_POSTING = {
    "source": "https://example.com/job/1",
    "company": "TestCorp",
    "title": "Machine Learning Engineer",
    "location": "Remote",
    "deadline": "2099-12-31",
    "raw_snippet": "Machine learning engineer role with TensorFlow and PyTorch. Build and deploy models.",
}


def _make_posting_payload(**overrides) -> dict:
    return {**SAMPLE_POSTING, **overrides}


class TestCreatePosting:
    async def test_create_single(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json=_make_posting_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "new"
        assert data["company"] == "TestCorp"
        assert data["fetch_attempts"] == 0

    async def test_create_sets_defaults(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json=_make_posting_payload())
        data = resp.json()
        assert data["status"] == "new"
        assert data["fetch_attempts"] == 0
        assert data["max_retries"] == 3
        assert data["relevance_score"] is None

    async def test_create_requires_source(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json={
            "company": "X", "title": "Y",
        })
        assert resp.status_code == 422

    async def test_create_requires_company(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json={
            "source": "https://example.com", "title": "Y",
        })
        assert resp.status_code == 422


class TestListPostings:
    async def test_list_empty(self, analyst_client):
        resp = await analyst_client.get("/api/postings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_after_create(self, analyst_client):
        await analyst_client.post("/api/postings", json=_make_posting_payload())
        await analyst_client.post("/api/postings", json=_make_posting_payload(
            source="https://example.com/job/2", company="OtherCorp",
        ))
        resp = await analyst_client.get("/api/postings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_filter_by_status(self, analyst_client):
        # Create a 'new' posting
        await analyst_client.post("/api/postings", json=_make_posting_payload())
        resp = await analyst_client.get("/api/postings?status=new")
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["status"] == "new" for p in data["items"])

    async def test_list_search(self, analyst_client):
        await analyst_client.post("/api/postings", json=_make_posting_payload())
        resp = await analyst_client.get("/api/postings?search=TestCorp")
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["company"] == "TestCorp" for p in data["items"])

    async def test_list_search_no_match(self, analyst_client):
        await analyst_client.post("/api/postings", json=_make_posting_payload())
        resp = await analyst_client.get("/api/postings?search=NOMATCH")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestGetPosting:
    async def test_get_detail(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json=_make_posting_payload())
        posting_id = resp.json()["id"]
        resp = await analyst_client.get(f"/api/postings/{posting_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == posting_id
        assert data["title"] == "Machine Learning Engineer"

    async def test_get_not_found(self, analyst_client):
        resp = await analyst_client.get("/api/postings/nonexistent-id")
        assert resp.status_code == 404


class TestUpdatePosting:
    async def test_update_status(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json=_make_posting_payload())
        posting_id = resp.json()["id"]
        resp = await analyst_client.patch(f"/api/postings/{posting_id}", json={
            "status": "fetch_failed",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "fetch_failed"

    async def test_update_invalid_status(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json=_make_posting_payload())
        posting_id = resp.json()["id"]
        resp = await analyst_client.patch(f"/api/postings/{posting_id}", json={
            "status": "bogus_status",
        })
        assert resp.status_code == 422

    async def test_update_not_found(self, analyst_client):
        resp = await analyst_client.patch("/api/postings/nonexistent-id", json={
            "status": "scored",
        })
        assert resp.status_code == 404


class TestDeletePosting:
    async def test_delete_by_admin(self, admin_client):
        resp = await admin_client.post("/api/postings", json=_make_posting_payload())
        posting_id = resp.json()["id"]
        resp = await admin_client.delete(f"/api/postings/{posting_id}")
        assert resp.status_code == 204
        # Verify deleted
        resp = await admin_client.get(f"/api/postings/{posting_id}")
        assert resp.status_code == 404

    async def test_delete_by_analyst_forbidden(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json=_make_posting_payload())
        posting_id = resp.json()["id"]
        resp = await analyst_client.delete(f"/api/postings/{posting_id}")
        assert resp.status_code == 403


class TestImportPostings:
    async def test_bulk_import(self, analyst_client):
        postings = [
            _make_posting_payload(source="https://example.com/1"),
            _make_posting_payload(source="https://example.com/2", company="Corp2"),
        ]
        resp = await analyst_client.post("/api/postings/import", json=postings)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 2
        assert all(p["status"] == "new" for p in data)


class TestFetchPosting:
    async def test_fetch_success(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json=_make_posting_payload())
        posting_id = resp.json()["id"]
        resp = await analyst_client.post(f"/api/postings/{posting_id}/fetch")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "scored"

    async def test_fetch_failure_marks_fetch_failed(self, analyst_client):
        """Issue #534: a failed fetch becomes fetch_failed, not expired."""
        resp = await analyst_client.post("/api/postings", json={
            "source": "https://example.com/dead",
            "company": "TestCorp",
            "title": "ML Engineer",
            "raw_snippet": "",  # empty → fetch fails
        })
        posting_id = resp.json()["id"]
        resp = await analyst_client.post(f"/api/postings/{posting_id}/fetch")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "fetch_failed"
        assert data["fetch_attempts"] == 1

    async def test_fetch_expired_rejected(self, analyst_client):
        resp = await analyst_client.post("/api/postings", json=_make_posting_payload())
        posting_id = resp.json()["id"]
        # Manually set to expired
        await analyst_client.patch(f"/api/postings/{posting_id}", json={"status": "expired"})
        resp = await analyst_client.post(f"/api/postings/{posting_id}/fetch")
        assert resp.status_code == 409