"""Job posting CRUD and lifecycle endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..core.security import CurrentUser
from ..models.orm import AuditLog, Posting
from ..models.schemas import (
    PostingCreate,
    PostingPage,
    PostingRead,
    PostingUpdate,
)
from ..services.lifecycle import default_fetch
from .deps import admin, analyst, viewer

router = APIRouter(prefix="/api/postings", tags=["postings"])


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
async def _audit(
    session: AsyncSession,
    user: CurrentUser,
    action: str,
    resource: str,
    detail: str = "",
) -> None:
    entry = AuditLog(
        user_id=user.sub, action=action, resource=resource, detail=detail
    )
    session.add(entry)


# -----------------------------------------------------------------------
# Read
# -----------------------------------------------------------------------
@router.get("/", response_model=PostingPage)
async def list_postings(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(viewer),
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, pattern=r"^(new|scored|fetch_failed|expired)$"),
    search: str | None = Query(default=None),
) -> PostingPage:
    stmt = select(Posting)
    if status:
        stmt = stmt.where(Posting.status == status)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            func.lower(Posting.title).like(func.lower(pattern))
            | func.lower(Posting.company).like(func.lower(pattern))
        )
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Posting.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    postings = result.scalars().all()
    pages = (total + page_size - 1) // page_size if page_size else 0
    return PostingPage(
        items=[PostingRead.model_validate(p) for p in postings],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{posting_id}", response_model=PostingRead)
async def get_posting(
    posting_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(viewer),
) -> PostingRead:
    posting = await session.get(Posting, posting_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="Posting not found")
    return PostingRead.model_validate(posting)


# -----------------------------------------------------------------------
# Create
# -----------------------------------------------------------------------
@router.post("/", response_model=PostingRead, status_code=status.HTTP_201_CREATED)
async def create_posting(
    payload: PostingCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(analyst),
) -> PostingRead:
    posting = Posting(
        source=payload.source,
        company=payload.company,
        title=payload.title,
        location=payload.location,
        deadline=payload.deadline,
        raw_snippet=payload.raw_snippet,
        description=payload.description,
        max_retries=payload.max_retries,
        status="new",
    )
    session.add(posting)
    await session.flush()
    await _audit(session, user, "create", "posting", f"id={posting.id} source={posting.source}")
    await session.commit()
    await session.refresh(posting)
    return PostingRead.model_validate(posting)


@router.post(
    "/import",
    response_model=list[PostingRead],
    status_code=status.HTTP_201_CREATED,
)
async def import_postings(
    payloads: list[PostingCreate],
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(analyst),
) -> list[PostingRead]:
    """Bulk import job postings (the first step of the pipeline)."""
    if len(payloads) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Import limit is 500 postings per request",
        )
    created_postings: list[Posting] = []
    for payload in payloads:
        posting = Posting(
            source=payload.source,
            company=payload.company,
            title=payload.title,
            location=payload.location,
            deadline=payload.deadline,
            raw_snippet=payload.raw_snippet,
            description=payload.description,
            max_retries=payload.max_retries,
            status="new",
        )
        session.add(posting)
        created_postings.append(posting)
    await session.flush()
    await _audit(session, user, "import", "posting", f"count={len(payloads)}")
    await session.commit()
    return [PostingRead.model_validate(p) for p in created_postings]


# -----------------------------------------------------------------------
# Update / delete
# -----------------------------------------------------------------------
@router.patch("/{posting_id}", response_model=PostingRead)
async def update_posting(
    posting_id: str,
    payload: PostingUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(analyst),
) -> PostingRead:
    posting = await session.get(Posting, posting_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="Posting not found")
    data = payload.model_dump(exclude_unset=True)
    changes = []
    for key, value in data.items():
        old = getattr(posting, key)
        setattr(posting, key, value)
        changes.append(f"{key}: {old!r} -> {value!r}")
    await _audit(session, user, "update", f"posting/{posting_id}", "; ".join(changes))
    await session.commit()
    await session.refresh(posting)
    return PostingRead.model_validate(posting)


@router.delete("/{posting_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_posting(
    posting_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(admin),
) -> None:
    posting = await session.get(Posting, posting_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="Posting not found")
    await session.delete(posting)
    await _audit(session, user, "delete", f"posting/{posting_id}", f"title={posting.title}")
    await session.commit()


# -----------------------------------------------------------------------
# Lifecycle actions
# -----------------------------------------------------------------------
@router.post("/{posting_id}/fetch", response_model=PostingRead)
async def fetch_posting(
    posting_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(analyst),
) -> PostingRead:
    """Manually trigger a fetch for a single posting (re-queues fetch_failed)."""
    posting = await session.get(Posting, posting_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="Posting not found")
    if posting.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot fetch an expired posting",
        )
    result = default_fetch(posting.source, posting.raw_snippet)
    if result.ok:
        posting.description = result.content
        posting.status = "scored"
        posting.scored_at = posting.scored_at or posting.created_at
        await _audit(session, user, "fetch", f"posting/{posting_id}", "ok")
    else:
        posting.fetch_attempts += 1
        posting.status = "fetch_failed"
        await _audit(session, user, "fetch", f"posting/{posting_id}", f"failed: {result.error}")
    await session.commit()
    await session.refresh(posting)
    return PostingRead.model_validate(posting)