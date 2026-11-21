"""Integration tests for the CV/tailor API endpoint."""
from __future__ import annotations

import pytest
from fastapi import status


CV_TAILOR_SAMPLE = {
    "cv_text": """
    experienced software engineer with Python and JavaScript development.
    Built web applications using React and Node.js.
    Familiar with SQL databases and Git version control.
    """,
    "posting_text": """
    we are looking for a senior software engineer with Python and machine learning.
    Experience with TensorFlow and PyTorch is required.
    Strong debugging skills and Git workflow experience needed.
    """,
}


class TestTailorCv:
    async def test_tailor_basic(self, analyst_client):
        """POST /api/cv/tailor returns keyword gaps between CV and posting."""
        payload = CV_TAILOR_SAMPLE
        resp = await analyst_client.post("/api/cv/tailor", json=payload)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        # Response should contain present and missing terms
        assert "present" in data
        assert "missing" in data
        assert "summary" in data
        assert isinstance(data["present"], list)
        assert isinstance(data["missing"], list)

        # "Python" should be present (in both CV and posting)
        present_lower = [t.lower() for t in data["present"]]
        assert "python" in present_lower

        # "machine learning" / "TensorFlow" should be missing from CV
        missing_terms = [t.lower() for t in data["missing"]]
        has_ml = any("machine learning" in t or "tensorflow" in t or "pytorch" in t for t in missing_terms)
        assert has_ml, f"Expected ML-related terms in missing, got: {data['missing']}"

    async def test_tailor_no_gaps(self, analyst_client):
        """CV covering all posting terms yields empty missing list."""
        cv_text = """
        Python software engineer with machine learning, TensorFlow, and PyTorch experience.
        """
        posting_text = """
        we are looking for a Python engineer with machine learning, TensorFlow, and PyTorch.
        """
        payload = {"cv_text": cv_text, "posting_text": posting_text}
        resp = await analyst_client.post("/api/cv/tailor", json=payload)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["missing"] == []

    async def test_tailor_empty_cv(self, analyst_client):
        """Empty CV text should report all posting terms as missing."""
        payload = {
            "cv_text": "",
            "posting_text": "Python developer with TensorFlow experience required.",
        }
        resp = await analyst_client.post("/api/cv/tailor", json=payload)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data["missing"]) > 0
        assert "python" in [t.lower() for t in data["missing"]]
        assert "tensorflow" in [t.lower() for t in data["missing"]]
