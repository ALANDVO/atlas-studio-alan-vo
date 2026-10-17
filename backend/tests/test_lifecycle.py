"""Tests for the posting lifecycle — the core of issue #534 fix.

Issue #534: a failed fetch must NOT be recorded as ``expired``.  Instead,
``fetch_failed`` is a retryable intermediate state.  Only a genuinely closed
posting (deadline passed) becomes ``expired``.
"""
from __future__ import annotations

import datetime

import pytest

from app.core.database import AsyncSessionFactory
from app.models.orm import Posting
from app.services.lifecycle import (
    PostingLifecycle,
    SimpleFetchResult,
)
from app.services.scorer import ScoringConfig


def _posting_kwargs(**overrides):
    """Build keyword arguments for a Posting."""
    defaults = dict(
        source="https://example.com/job/1",
        company="TestCorp",
        title="Machine Learning Engineer",
        location="Remote",
        deadline="2099-12-31",
        raw_snippet="Machine learning engineer role with TensorFlow and PyTorch.",
        status="new",
        fetch_attempts=0,
        max_retries=3,
    )
    defaults.update(overrides)
    return defaults


async def _make_posting(session, **kwargs) -> Posting:
    p = Posting(**_posting_kwargs(**kwargs))
    session.add(p)
    await session.flush()
    return p


class TestCandidateSelection:
    """Issue #534: fetch_failed is retryable, not terminal."""

    async def test_new_is_candidate(self):
        async with AsyncSessionFactory() as session:
            p = await _make_posting(session, status="new")
            await session.commit()
            lifecycle = PostingLifecycle(session)
            candidates = await lifecycle.select_candidates()
            ids = [c.id for c in candidates]
            assert p.id in ids

    async def test_scored_not_candidate(self):
        async with AsyncSessionFactory() as session:
            p = await _make_posting(session, status="scored")
            await session.commit()
            lifecycle = PostingLifecycle(session)
            candidates = await lifecycle.select_candidates()
            assert p.id not in [c.id for c in candidates]

    async def test_expired_not_candidate(self):
        async with AsyncSessionFactory() as session:
            p = await _make_posting(session, status="expired")
            await session.commit()
            lifecycle = PostingLifecycle(session)
            candidates = await lifecycle.select_candidates()
            assert p.id not in [c.id for c in candidates]

    async def test_fetch_failed_retryable_is_candidate(self):
        async with AsyncSessionFactory() as session:
            p = await _make_posting(session, status="fetch_failed", fetch_attempts=1)
            await session.commit()
            lifecycle = PostingLifecycle(session)
            candidates = await lifecycle.select_candidates()
            assert p.id in [c.id for c in candidates]

    async def test_fetch_failed_max_retries_not_candidate(self):
        async with AsyncSessionFactory() as session:
            p = await _make_posting(session, status="fetch_failed", fetch_attempts=3, max_retries=3)
            await session.commit()
            lifecycle = PostingLifecycle(session)
            candidates = await lifecycle.select_candidates()
            assert p.id not in [c.id for c in candidates]


class TestScoringRound:
    """Issue #534: fetch failure → fetch_failed, never expired."""

    async def test_failed_fetch_goes_to_fetch_failed(self):
        async with AsyncSessionFactory() as session:
            # Empty snippet → fetch fails
            p = await _make_posting(session, status="new", raw_snippet="")
            await session.commit()
            lifecycle = PostingLifecycle(
                session,
                fetch_fn=lambda s, snip: SimpleFetchResult(ok=False, error="404 not found"),
            )
            result = await lifecycle.run_scoring_round()
            assert result["fetch_failed"] >= 1
            await session.refresh(p)
            # Core fix: fetch failure is fetch_failed, NOT expired
            assert p.status == "fetch_failed"
            assert p.fetch_attempts == 1

    async def test_successful_fetch_goes_to_scored(self):
        async with AsyncSessionFactory() as session:
            p = await _make_posting(
                session, status="new",
                raw_snippet="machine learning tensorflow pytorch python model",
            )
            await session.commit()
            lifecycle = PostingLifecycle(
                session,
                fetch_fn=lambda s, snip: SimpleFetchResult(ok=True, content=snip),
            )
            result = await lifecycle.run_scoring_round()
            assert result["scored"] >= 1
            await session.refresh(p)
            assert p.status == "scored"
            assert p.relevance_score is not None
            assert 0.0 <= p.relevance_score <= 1.0

    async def test_fetch_failed_remains_retryable(self):
        """A second scoring round retries a fetch_failed posting with attempts < max."""
        async with AsyncSessionFactory() as session:
            p = await _make_posting(session, status="new", raw_snippet="")
            await session.commit()
            lifecycle = PostingLifecycle(
                session,
                fetch_fn=lambda s, snip: SimpleFetchResult(ok=False, error="timeout"),
            )
            await lifecycle.run_scoring_round()
            await session.refresh(p)
            assert p.status == "fetch_failed"
            assert p.fetch_attempts == 1

            # Second attempt — fetch now succeeds
            lifecycle2 = PostingLifecycle(
                session,
                fetch_fn=lambda s, snip: SimpleFetchResult(ok=True, content=snip),
            )
            result2 = await lifecycle2.run_scoring_round()
            assert result2["scored"] >= 1
            await session.refresh(p)
            assert p.status == "scored"

    async def test_fetch_failed_reaches_max_retries(self):
        """After max_retries failed attempts, posting is no longer a candidate."""
        async with AsyncSessionFactory() as session:
            p = await _make_posting(session, status="new", raw_snippet="", max_retries=2)
            await session.commit()
            lifecycle = PostingLifecycle(
                session,
                fetch_fn=lambda s, snip: SimpleFetchResult(ok=False, error="403 forbidden"),
            )
            # First round
            await lifecycle.run_scoring_round()
            await session.refresh(p)
            assert p.status == "fetch_failed"
            assert p.fetch_attempts == 1

            # Second round
            await lifecycle.run_scoring_round()
            await session.refresh(p)
            assert p.fetch_attempts == 2

            # Third round — should NOT be a candidate (attempts >= max_retries)
            candidates_before = await lifecycle.select_candidates()
            assert p.id not in [c.id for c in candidates_before]

    async def test_past_deadline_expired_not_scored(self):
        """Issue #534: a posting whose deadline passed is retired to ``expired``
        by the sweep that opens the scoring round — it is never scored."""
        past = (
            datetime.date.today() - datetime.timedelta(days=1)
        ).isoformat()
        async with AsyncSessionFactory() as session:
            p = await _make_posting(
                session, status="new", deadline=past,
                raw_snippet="machine learning python tensorflow pytorch",
            )
            await session.commit()
            lifecycle = PostingLifecycle(
                session,
                fetch_fn=lambda s, snip: SimpleFetchResult(ok=True, content=snip),
            )
            result = await lifecycle.run_scoring_round()
            await session.refresh(p)
            assert p.status == "expired"
            assert result["expired"] >= 1
            assert result["scored"] == 0


class TestSweep:
    """The sweep only writes 'expired' for genuinely closed postings."""

    async def test_sweep_retires_past_deadline(self):
        async with AsyncSessionFactory() as session:
            p = await _make_posting(session, status="scored", deadline="2020-01-01")
            await session.commit()
            lifecycle = PostingLifecycle(session)
            result = await lifecycle.sweep()
            assert result["expired"] >= 1
            await session.refresh(p)
            assert p.status == "expired"

    async def test_sweep_keeps_future_deadline(self):
        async with AsyncSessionFactory() as session:
            p = await _make_posting(session, status="scored", deadline="2099-12-31")
            await session.commit()
            lifecycle = PostingLifecycle(session)
            result = await lifecycle.sweep()
            assert result["expired"] == 0
            await session.refresh(p)
            assert p.status == "scored"

    async def test_sweep_keeps_fetch_failed_with_future_deadline(self):
        """Issue #534: a fetch failure is never retired to expired by the sweep."""
        async with AsyncSessionFactory() as session:
            p = await _make_posting(
                session, status="fetch_failed", deadline="2099-12-31",
                fetch_attempts=1,
            )
            await session.commit()
            lifecycle = PostingLifecycle(session)
            result = await lifecycle.sweep()
            assert result["expired"] == 0
            await session.refresh(p)
            assert p.status == "fetch_failed"

    async def test_sweep_keeps_null_deadline(self):
        """Postings with no deadline are never expired by the sweep."""
        async with AsyncSessionFactory() as session:
            p = await _make_posting(session, status="scored", deadline=None)
            await session.commit()
            lifecycle = PostingLifecycle(session)
            result = await lifecycle.sweep()
            assert result["expired"] == 0
            await session.refresh(p)
            assert p.status == "scored"