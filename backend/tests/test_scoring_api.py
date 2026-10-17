"""Integration tests for the scoring API — the end-to-end pipeline."""
from __future__ import annotations

import datetime

import pytest


POSTING_A = {
    "source": "https://example.com/job/1",
    "company": "ML Corp",
    "title": "Machine Learning Engineer",
    "location": "Remote",
    "deadline": "2099-12-31",
    "raw_snippet": "Build ML models with TensorFlow and PyTorch. Python, scikit-learn, model deployment on GCP.",
}

POSTING_B = {
    "source": "https://example.com/job/2",
    "company": "Sales Inc",
    "title": "Sales Representative",
    "location": "NYC",
    "deadline": "2099-12-31",
    "raw_snippet": "B2B sales of enterprise software. Quota, CRM, pipeline management.",
}

POSTING_C = {
    "source": "https://example.com/job/3",
    "company": "Data Co",
    "title": "Data Scientist",
    "location": "SF",
    "deadline": "2099-12-31",
    "raw_snippet": "Build recommendation systems and deep learning models. PyTorch, Python, MLflow.",
}


class TestScoringRun:
    async def test_run_scoring_pipeline(self, analyst_client):
        # Import postings
        await analyst_client.post("/api/postings", json=POSTING_A)
        await analyst_client.post("/api/postings", json=POSTING_B)
        await analyst_client.post("/api/postings", json=POSTING_C)

        # Run scoring
        resp = await analyst_client.post("/api/scoring/run", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["scored"] == 3  # all have snippets, so fetch succeeds

        # ML postings should score higher than sales
        by_id = {p["id"]: p for p in data["scored_postings"]}
        ml_scores = [p["relevance_score"] for p in by_id.values()
                     if "ML" in p["company"] or "Data" in p["company"]]
        sales_scores = [p["relevance_score"] for p in by_id.values()
                        if "Sales" in p["company"]]
        assert max(ml_scores) > min(ml_scores) or len(ml_scores) == 1
        assert max(ml_scores) > max(sales_scores)

    async def test_scoring_with_custom_profile(self, analyst_client):
        await analyst_client.post("/api/postings", json=POSTING_A)
        resp = await analyst_client.post("/api/scoring/run", json={
            "profile": {
                "title": "Data Scientist",
                "description": "deep learning recommendation systems pytorch",
                "keywords": ["pytorch", "recommendation", "deep learning"],
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_title"] == "Data Scientist"

    async def test_run_scoring_no_candidates(self, analyst_client):
        resp = await analyst_client.post("/api/scoring/run", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["scored"] == 0

    async def test_scoring_run_recorded(self, analyst_client):
        await analyst_client.post("/api/postings", json=POSTING_A)
        resp = await analyst_client.post("/api/scoring/run", json={})
        data = resp.json()
        run_id = data["run_id"]
        resp = await analyst_client.get(f"/api/scoring/runs/{run_id}")
        assert resp.status_code == 200
        run_data = resp.json()
        assert run_data["target_profile"] == "Machine Learning Engineer"


class TestScoringEvaluate:
    async def test_evaluate_returns_metrics(self, analyst_client):
        resp = await analyst_client.get("/api/scoring/evaluate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset"] == "labeled_postings"
        assert data["num_examples"] == 10
        assert "metrics" in data
        metrics = data["metrics"]
        assert "precision@3" in metrics
        assert "recall@3" in metrics
        assert "map" in metrics
        assert "ndcg@3" in metrics
        assert metrics["num_relevant"] == 5  # 5 relevant examples in fixture

    async def test_evaluate_is_deterministic(self, analyst_client):
        resp1 = await analyst_client.get("/api/scoring/evaluate")
        resp2 = await analyst_client.get("/api/scoring/evaluate")
        assert resp1.json() == resp2.json()

    async def test_evaluate_top5_sorted(self, analyst_client):
        resp = await analyst_client.get("/api/scoring/evaluate")
        data = resp.json()
        top5 = data["top_5"]
        assert len(top5) <= 5
        # Scores should be descending
        scores = [item["score"] for item in top5]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]


class TestScoringExplain:
    async def test_explain_without_api_key_returns_501(self, analyst_client):
        # Create and score a posting
        resp = await analyst_client.post("/api/postings", json=POSTING_A)
        posting_id = resp.json()["id"]
        await analyst_client.post("/api/scoring/run", json={})

        resp = await analyst_client.post("/api/scoring/explain", json={
            "posting_id": posting_id,
            "profile": {
                "title": "Machine Learning Engineer",
                "description": "tensorflow pytorch python",
                "keywords": ["ml", "tensorflow"],
            },
        })
        # No LLM_API_KEY configured → 501 with clear error
        assert resp.status_code == 501
        assert "LLM_API_KEY" in resp.json()["detail"]

    async def test_explain_not_found_posting(self, analyst_client):
        resp = await analyst_client.post("/api/scoring/explain", json={
            "posting_id": "nonexistent-id",
            "profile": {
                "title": "Machine Learning Engineer",
                "description": "tensorflow",
                "keywords": [],
            },
        })
        assert resp.status_code == 404


class TestSweepEndpoint:
    async def test_sweep_endpoint_expires_past_deadline(self, analyst_client):
        past = (
            datetime.date.today() - datetime.timedelta(days=1)
        ).isoformat()
        resp = await analyst_client.post("/api/postings", json={**POSTING_A, "deadline": past})
        assert resp.status_code == 201
        posting_id = resp.json()["id"]

        resp = await analyst_client.post("/api/scoring/sweep")
        assert resp.status_code == 200
        assert resp.json()["expired"] >= 1

        detail = await analyst_client.get(f"/api/postings/{posting_id}")
        assert detail.json()["status"] == "expired"

    async def test_run_retires_past_deadline_to_expired(self, analyst_client):
        past = (
            datetime.date.today() - datetime.timedelta(days=1)
        ).isoformat()
        resp = await analyst_client.post("/api/postings", json={**POSTING_A, "deadline": past})
        assert resp.status_code == 201
        posting_id = resp.json()["id"]

        resp = await analyst_client.post("/api/scoring/run", json={})
        assert resp.status_code == 200
        data = resp.json()
        # Past-deadline posting is retired to expired, never scored.
        assert data["expired"] >= 1
        assert data["scored"] == 0

        detail = await analyst_client.get(f"/api/postings/{posting_id}")
        assert detail.json()["status"] == "expired"

    async def test_sweep_rejects_unauthenticated(self, client):
        resp = await client.post("/api/scoring/sweep")
        assert resp.status_code == 401