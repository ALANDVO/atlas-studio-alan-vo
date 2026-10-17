"""Pydantic request/response schemas for the Atlas Studio API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PostingBase(BaseModel):
    source: str = Field(..., max_length=512, description="Original URL or source identifier")
    company: str = Field(..., max_length=256)
    title: str = Field(..., max_length=256)
    location: str = Field(default="", max_length=256)
    deadline: str | None = Field(default=None, description="ISO date string YYYY-MM-DD")
    raw_snippet: str = Field(default="", description="Initial imported text snippet")
    max_retries: int = Field(default=3, ge=0, le=10)


class PostingCreate(PostingBase):
    description: str = Field(default="", description="Full posting body (may be fetched later)")


class PostingUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(new|scored|fetch_failed|expired)$")
    description: str | None = None
    relevance_score: float | None = None
    relevance_explanation: str | None = None


class PostingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    company: str
    title: str
    location: str
    deadline: str | None
    raw_snippet: str
    description: str
    status: str
    fetch_attempts: int
    max_retries: int
    relevance_score: float | None
    relevance_explanation: str
    scored_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PostingPage(BaseModel):
    """Paginated list of postings."""

    items: list[PostingRead]
    total: int
    page: int
    page_size: int
    pages: int


class ScoringRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_profile: str
    scored_count: int
    failed_count: int
    expired_count: int
    results_json: str
    created_at: datetime


class TargetProfile(BaseModel):
    """A target role profile for relevance scoring."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., description="Target job title, e.g. 'Machine Learning Engineer'")
    description: str = Field(..., description="Target role description / responsibilities")
    keywords: list[str] = Field(default_factory=list)


class ScoredPosting(BaseModel):
    id: str
    source: str
    company: str
    title: str
    location: str
    relevance_score: float
    relevance_explanation: str
    status: str


class ScoringResult(BaseModel):
    run_id: str
    target_title: str
    total: int
    scored: int
    fetch_failed: int
    expired: int
    scored_postings: list[ScoredPosting]


class ExplainRequest(BaseModel):
    posting_id: str
    target: TargetProfile


class LoginResponse(BaseModel):
    user: dict[str, str]
    csrf_token: str


class UserRead(BaseModel):
    sub: str
    role: str
    name: str


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "atlas-studio"
    version: str