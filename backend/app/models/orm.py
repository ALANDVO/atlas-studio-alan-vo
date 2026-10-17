"""SQLAlchemy ORM models for Atlas Studio."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str] = mapped_column(String(128))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )


class Posting(Base):
    """A tracked job posting through its lifecycle.

    Status semantics (see issue #534):
      new         — imported, not yet scored
      fetch_failed— transient fetch error, retryable (retry_count < max_retries)
      scored      — fetched + scored successfully
      expired     — deadline passed or page states it is closed (terminal)
    """

    __tablename__ = "postings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    source: Mapped[str] = mapped_column(String(512))
    company: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(256))
    location: Mapped[str] = mapped_column(String(256), default="")
    deadline: Mapped[str | None] = mapped_column(String(16), default=None)
    raw_snippet: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(24), default="new", index=True
    )
    fetch_attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    relevance_score: Mapped[float | None] = mapped_column(Float, default=None)
    relevance_explanation: Mapped[str] = mapped_column(Text, default="")
    scored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    __table_args__ = (
        Index("ix_postings_status_score", "status", "relevance_score"),
        Index("ix_postings_company_title", "company", "title"),
    )


class ScoringRun(Base):
    """A recorded run of the scoring pipeline."""

    __tablename__ = "scoring_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    target_profile: Mapped[str] = mapped_column(Text)
    scored_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    expired_count: Mapped[int] = mapped_column(Integer, default=0)
    results_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )


class LabelingExample(Base):
    """A human-labeled job posting used for scorer evaluation."""

    __tablename__ = "labeling_examples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    title: Mapped[str] = mapped_column(String(256))
    company: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    label: Mapped[int] = mapped_column(Integer)  # 1 = relevant, 0 = not relevant
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )