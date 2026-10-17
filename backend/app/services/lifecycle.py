"""Posting lifecycle management.

Issue #534: a failed fetch must NOT be recorded as ``expired``.  Instead,
``fetch_failed`` is a retryable intermediate state.  Only a genuinely closed
posting (deadline passed or page states it is closed) becomes ``expired``.

Status diagram:

    new ──fetch+score──> scored
      └──fetch fails──> fetch_failed  (retry_count < max_retries → retryable)
      └──deadline pass──> expired      (terminal)

Candidates for the next scoring round are: ``new`` OR
(``fetch_failed`` AND ``retry_count < max_retries``).
"""
from __future__ import annotations

import datetime as _dt
from typing import Callable, Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.orm import Posting
from .scorer import ScoredItem, ScoringConfig, TFIDFScorer


# ---------------------------------------------------------------------------
# Fetch strategy (pluggable — real impl uses httpx against the posting URL)
# ---------------------------------------------------------------------------
class FetchResult(Protocol):
    """Result of attempting to fetch a posting's full content."""

    ok: bool
    content: str
    error: str


class SimpleFetchResult:
    __slots__ = ("ok", "content", "error")

    def __init__(self, ok: bool, content: str = "", error: str = ""):
        self.ok = ok
        self.content = content
        self.error = error


FetchFn = Callable[[str, str], FetchResult]


def default_fetch(source: str, snippet: str) -> FetchResult:
    """Default fetch strategy for the deterministic core.

    In a real deployment this would issue an HTTP GET to *source* and parse
    the HTML.  For the offline-first core we treat the *snippet* as the
    posting body (simulating a successful local archive) when it is non-empty,
    and report a fetch failure otherwise.
    """
    if snippet and len(snippet) >= 10:
        return SimpleFetchResult(ok=True, content=snippet)
    if source.startswith("http"):
        # Simulate a 404 / login-wall on an empty remote posting.
        return SimpleFetchResult(ok=False, error="simulated 404 / login wall")
    return SimpleFetchResult(ok=False, error="no local source available")


# ---------------------------------------------------------------------------
# Lifecycle engine
# ---------------------------------------------------------------------------
class PostingLifecycle:
    """Manages the posting status lifecycle and scoring round."""

    def __init__(
        self,
        session: AsyncSession,
        config: ScoringConfig | None = None,
        fetch_fn: FetchFn = default_fetch,
    ):
        self.session = session
        self.config = config or ScoringConfig()
        self._fetch_fn = fetch_fn
        self._scorer: TFIDFScorer | None = None

    @property
    def scorer(self) -> TFIDFScorer:
        if self._scorer is None:
            self._scorer = TFIDFScorer(self.config)
        return self._scorer

    # ------------------------------------------------------------------
    # Candidate selection (issue #534: fetch_failed is retryable)
    # ------------------------------------------------------------------
    async def select_candidates(self) -> list[Posting]:
        """Select postings eligible for a scoring round.

        Candidates are ``new`` postings OR ``fetch_failed`` postings whose
        ``retry_count`` is below ``max_retries``.  ``expired`` and ``scored``
        are excluded.
        """
        stmt = select(Posting).where(
            Posting.status.in_(["new", "fetch_failed"])
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        candidates: list[Posting] = []
        for row in rows:
            if row.status == "new":
                candidates.append(row)
            elif row.fetch_attempts < row.max_retries:
                candidates.append(row)
        return candidates

    # ------------------------------------------------------------------
    # Scoring round
    # ------------------------------------------------------------------
    async def run_scoring_round(self) -> dict:
        """Run one scoring round over all candidate postings.

        First retires past-deadline postings to ``expired`` (terminal) — the
        only path that writes ``expired``; a fetch failure stays
        ``fetch_failed`` and remains retryable (issue #534).  Then, for each
        candidate:
          1. Attempt fetch.
          2. If fetch succeeds → status = ``scored``, compute relevance.
          3. If fetch fails → status = ``fetch_failed``, increment attempt.

        Returns a summary dict with counts including ``expired``.
        """
        expired = (await self.sweep())["expired"]

        candidates = await self.select_candidates()
        if not candidates:
            return {"scored": 0, "fetch_failed": 0, "expired": expired, "candidates": 0}

        # Fit the scorer on all posting texts so IDF is corpus-aware.
        texts = []
        for posting in candidates:
            text = self._posting_text(posting)
            texts.append(text if text else "(empty)")
        self.scorer.fit(texts)

        scored = 0
        fetch_failed = 0
        scored_items: list[ScoredItem] = []

        for posting in candidates:
            result = self._fetch_fn(posting.source, posting.raw_snippet)
            if result.ok:
                posting.description = result.content
                posting.status = "scored"
                posting.scored_at = _dt.datetime.now(_dt.timezone.utc)
                text = self._posting_text(posting)
                score, matched = self.scorer.score_posting(text)
                posting.relevance_score = score
                posting.relevance_explanation = (
                    ScoredItem(
                        id=posting.id,
                        source=posting.source,
                        company=posting.company,
                        title=posting.title,
                        location=posting.location,
                        score=score,
                        matched_terms=matched,
                        status="scored",
                    ).to_explanation()
                )
                scored += 1
                scored_items.append(
                    ScoredItem(
                        id=posting.id,
                        source=posting.source,
                        company=posting.company,
                        title=posting.title,
                        location=posting.location,
                        score=score,
                        matched_terms=matched,
                        status="scored",
                    )
                )
            else:
                posting.fetch_attempts += 1
                posting.status = "fetch_failed"
                posting.relevance_score = None
                # Keep retryable: only mark abandoned (max_retries reached)
                # by updating the status text, but keep as fetch_failed so
                # the report can list it separately.
                fetch_failed += 1
                scored_items.append(
                    ScoredItem(
                        id=posting.id,
                        source=posting.source,
                        company=posting.company,
                        title=posting.title,
                        location=posting.location,
                        score=0.0,
                        matched_terms=[],
                        status="fetch_failed",
                    )
                )

        await self.session.commit()
        return {
            "scored": scored,
            "fetch_failed": fetch_failed,
            "expired": expired,
            "candidates": len(candidates),
            "scored_items": scored_items,
        }

    # ------------------------------------------------------------------
    # Sweep: retire past-deadline postings to expired (terminal)
    # ------------------------------------------------------------------
    async def sweep(self, now: datetime | None = None) -> dict:
        """Retire postings whose deadline has passed to ``expired``.

        This is the ONLY path that should write ``expired``.  A fetch failure
        must never reach ``expired`` — it stays as ``fetch_failed`` so it can
        be retried.
        """
        if now is None:
            now = _dt.datetime.now(_dt.timezone.utc)
        today = now.date().isoformat()
        stmt = (
            update(Posting)
            .where(Posting.deadline <= today)
            .where(Posting.status != "expired")
            .values(status="expired")
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return {"expired": result.rowcount}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _posting_text(posting: Posting) -> str:
        return f"{posting.title} {posting.company} {posting.description}".strip()

    @staticmethod
    def is_retryable(posting: Posting) -> bool:
        """True if a fetch_failed posting can still be retried."""
        return posting.status == "fetch_failed" and posting.fetch_attempts < posting.max_retries