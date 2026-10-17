"""Scoring pipeline endpoints: run, evaluate, opt-in explain."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_session
from ..core.security import CurrentUser
from ..models.orm import AuditLog, ScoringRun
from ..models.schemas import ScoringResult, ScoringRunRead, TargetProfile
from ..services.lifecycle import PostingLifecycle
from ..services.llm import LLMConfig, LLMAdvisor
from ..services.scorer import (
    ScoredItem,
    ScoringConfig,
    TFIDFScorer,
    evaluate,
)
from .deps import analyst, get_lifecycle

router = APIRouter(prefix="/api/scoring", tags=["scoring"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


class ScoringRunRequest(BaseModel):
    """Optional target profile override; defaults come from settings/config."""

    profile: TargetProfile | None = Field(default=None)


@router.post("/run", response_model=ScoringResult)
async def run_scoring(
    request: ScoringRunRequest | None = None,
    lifecycle: PostingLifecycle = Depends(get_lifecycle),
    user: CurrentUser = Depends(analyst),
) -> ScoringResult:
    """Run one scoring round over all candidate postings.

    Addresses issue #534: candidates include ``new`` AND ``fetch_failed``
    postings whose retry count is below the cap.  A fetch failure becomes
    ``fetch_failed`` (retryable), never ``expired``.
    """
    if request and request.profile:
        lifecycle.config = ScoringConfig(
            target_title=request.profile.title,
            target_description=request.profile.description,
            keywords=request.profile.keywords,
            max_retries=lifecycle.config.max_retries,
        )

    result = await lifecycle.run_scoring_round()
    scored_items: list[ScoredItem] = result.get("scored_items", [])
    scored_postings = [
        {
            "id": item.id,
            "source": item.source,
            "company": item.company,
            "title": item.title,
            "location": item.location,
            "relevance_score": item.score,
            "relevance_explanation": item.matched_terms and item.to_explanation() or "",
            "status": item.status,
        }
        for item in scored_items
    ]
    run = ScoringRun(
        target_profile=lifecycle.config.target_title,
        scored_count=result["scored"],
        failed_count=result["fetch_failed"],
        expired_count=result["expired"],
        results_json=json.dumps(scored_postings),
    )
    lifecycle.session.add(run)
    await lifecycle.session.commit()
    await lifecycle.session.refresh(run)

    return ScoringResult(
        run_id=run.id,
        target_title=lifecycle.config.target_title,
        total=len(scored_items),
        scored=result["scored"],
        fetch_failed=result["fetch_failed"],
        expired=result["expired"],
        scored_postings=[_item_to_schema(item) for item in scored_items],
    )


@router.post("/sweep")
async def sweep_postings(
    lifecycle: PostingLifecycle = Depends(get_lifecycle),
    user: CurrentUser = Depends(analyst),
) -> dict:
    """Retire past-deadline postings to ``expired`` (terminal).

    This is the only operation that writes ``expired``.  A fetch failure is
    never retired here — it stays ``fetch_failed`` and remains retryable
    (issue #534: a failed fetch must never become a closed posting).
    """
    result = await lifecycle.sweep()
    lifecycle.session.add(
        AuditLog(user_id=user.sub, action="sweep", resource="postings",
                detail=f"retired {result['expired']} past-deadline posting(s) to expired")
    )
    await lifecycle.session.commit()
    return {"expired": result["expired"]}


def _item_to_schema(item: ScoredItem) -> dict:
    return {
        "id": item.id,
        "source": item.source,
        "company": item.company,
        "title": item.title,
        "location": item.location,
        "relevance_score": round(item.score, 4),
        "relevance_explanation": item.to_explanation() if item.matched_terms else "",
        "status": item.status,
    }


@router.get("/evaluate")
async def evaluate_scorer(
    user: CurrentUser = Depends(analyst),
    dataset: str = Query(default="labeled_postings"),
) -> dict:
    """Evaluate the TF-IDF scorer against a labeled dataset.

    Loads ``data/<dataset>.json``, scores all examples against the target
    profile, and returns IR metrics (Precision@k, MAP, NDCG).  Deterministic.
    """
    path = DATA_DIR / f"{dataset}.json"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Labeled dataset not found: {path}",
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    target_data = data["target"]
    examples = data["examples"]

    config = ScoringConfig(
        target_title=target_data["title"],
        target_description=target_data.get("description", ""),
        keywords=target_data.get("keywords", []),
    )
    scorer = TFIDFScorer(config)
    texts = [e["description"] or e["title"] for e in examples]
    scorer.fit(texts)

    scored: list[ScoredItem] = []
    for ex in examples:
        text = (ex.get("description") or "") + " " + (ex.get("title") or "")
        score, matched = scorer.score_posting(text)
        scored.append(
            ScoredItem(
                id=ex["id"],
                source=ex.get("source", ""),
                company=ex.get("company", ""),
                title=ex.get("title", ""),
                location=ex.get("location", ""),
                score=score,
                matched_terms=matched,
            )
        )

    ranked = sorted(scored, key=lambda x: x.score, reverse=True)
    labels = {ex["id"]: ex["label"] for ex in examples}
    metrics = evaluate(ranked, labels)
    return {
        "dataset": dataset,
        "target_title": config.target_title,
        "num_examples": len(examples),
        "metrics": metrics,
        "top_5": [
            {"id": item.id, "title": item.title, "score": round(item.score, 4), "label": labels.get(item.id, 0)}
            for item in ranked[:5]
        ],
    }


class ExplainRequest(BaseModel):
    posting_id: str
    profile: TargetProfile | None = Field(default=None)


@router.post("/explain")
async def explain_scoring(
    request: ExplainRequest,
    user: CurrentUser = Depends(analyst),
) -> dict:
    """Opt-in LLM explanation for a scored posting.

    Grounded in actual TF-IDF matched terms.  Raises a clear error if no
    LLM_API_KEY is configured — never fabricates a response.
    """
    # Look up the posting first (404 before 501 for unknown IDs).
    from ..core.database import AsyncSessionFactory
    from ..models.orm import Posting

    async with AsyncSessionFactory() as session:
        posting = await session.get(Posting, request.posting_id)
        if posting is None:
            raise HTTPException(status_code=404, detail="Posting not found")
        if posting.status != "scored" or posting.relevance_score is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Posting must be scored before LLM explanation is available.",
            )
        # Parse matched terms from the stored explanation text.
        matched_terms: list[str] = []
        if posting.relevance_explanation:
            import re as _re

            match = _re.search(r"matched terms: (.+)\.", posting.relevance_explanation)
            if match:
                matched_terms = [
                    t.strip() for t in match.group(1).split(",") if t.strip()
                ]

    if not settings.llm_api_key:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="LLM explanation is opt-in. Set LLM_API_KEY to enable.",
        )

    config = ScoringConfig(
        target_title=request.profile.title if request.profile else settings.app_name,
        target_description=request.profile.description if request.profile else "",
        keywords=request.profile.keywords if request.profile else [],
    )
    advisor = LLMAdvisor(
        LLMConfig(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    )
    explanation = await advisor.explain_scoring(
        posting_title=posting.title,
        posting_company=posting.company,
        matched_terms=matched_terms,
        score=posting.relevance_score or 0.0,
    )
    return {
        "type": "advisory",
        "posting_id": posting.id,
        "score": posting.relevance_score,
        "explanation": explanation,
    }


@router.get("/runs/{run_id}", response_model=ScoringRunRead)
async def get_scoring_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(analyst),
) -> ScoringRunRead:
    run = await session.get(ScoringRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scoring run not found")
    return ScoringRunRead.model_validate(run)