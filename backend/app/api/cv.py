"""CV/resume tailoring endpoints."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from ..services.cv_tailor import find_keyword_gaps, summarize_gaps, s

router = APIRouter(prefix="/api/cv", tags=["cv"])


class CvTailorRequest(BaseModel):
    """Request to tailor a CV to a job posting.

    - cv_text: the base CV/resume content
    - posting_text: the job posting content
    """
    cv_text: str = Field(..., description="Base CV/resume text")
    posting_text: str = Field(..., description="Job posting text")


class CvTailorResponse(BaseModel):
    """Response with keyword gaps and summary."""
    cv_terms: list[str]
    posting_terms: list[str]
    present: list[str]
    missing: list[str]
    summary: str


@router.post(
    "/tailor",
    response_model=CvTailorResponse,
    summary="Analyze a posting against a base CV and return keyword gaps",
)
async def tailor_cv(
    request: CvTailorRequest = Body(...),
) -> CvTailorResponse:
    """Analyze a posting against a base CV and return keyword gaps.

    Returns which posting terms are present in the CV and which are missing,
    plus a human-readable summary.
    """
    gaps = find_keyword_gaps(request.cv_text, request.posting_text)
    return CvTailorResponse(
        cv_terms=sorted(gaps["cv_terms"]),
        posting_terms=sorted(gaps["posting_terms"]),
        present=gaps["present"],
        missing=gaps["missing"],
        summary=summarize_gaps(gaps),
    )
