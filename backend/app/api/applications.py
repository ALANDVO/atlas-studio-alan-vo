"""Job application tracking endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..core.security import CurrentUser
from ..models.orm import Application, AuditLog, Posting
from ..models.schemas import (
    ApplicationCreate,
    ApplicationPage,
    ApplicationRead,
    ApplicationUpdate,
)
from .deps import analyst, viewer

router = APIRouter(prefix="/api/applications", tags=["applications"])

VALID_STAGES = {"applied", "screening", "interview", "offer", "rejected", "withdrawn"}


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


@router.get("/", response_model=ApplicationPage)
async def list_applications(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(viewer),
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=20, ge=1, le=100),
    stage: str | None = Query(default=None),
) -> ApplicationPage:
    stmt = select(Application)
    count_stmt = select(func.count()).select_from(Application)
    if stage:
        if stage not in VALID_STAGES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid stage: {stage}. Must be one of {sorted(VALID_STAGES)}",
            )
        stmt = stmt.where(Application.stage == stage)
        count_stmt = count_stmt.where(Application.stage == stage)

    total = await session.scalar(count_stmt)
    stmt = (
        stmt.order_by(Application.applied_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()

    pages = max(1, (total + page_size - 1) // page_size) if total else 0
    return ApplicationPage(
        items=[ApplicationRead.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{application_id}", response_model=ApplicationRead)
async def get_application(
    application_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(viewer),
) -> ApplicationRead:
    application = await session.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationRead.model_validate(application)


@router.post("/", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(analyst),
) -> ApplicationRead:
    if payload.stage not in VALID_STAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid stage: {payload.stage}",
        )
    # Verify posting exists.
    posting = await session.get(Posting, payload.posting_id)
    if not posting:
        raise HTTPException(status_code=404, detail="Posting not found")

    application = Application(
        posting_id=payload.posting_id,
        stage=payload.stage,
        notes=payload.notes,
    )
    session.add(application)
    await session.flush()
    await _audit(session, user, "application.create", application.id, posting.title or "")
    await session.commit()
    await session.refresh(application)
    return ApplicationRead.model_validate(application)


@router.patch("/{application_id}", response_model=ApplicationRead)
async def update_application(
    application_id: str,
    payload: ApplicationUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(analyst),
) -> ApplicationRead:
    application = await session.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if payload.stage is not None:
        if payload.stage not in VALID_STAGES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid stage: {payload.stage}",
            )
        application.stage = payload.stage
    if payload.notes is not None:
        application.notes = payload.notes
    await _audit(session, user, "application.update", application.id, str(payload.model_dump(exclude_none=True)))
    await session.commit()
    await session.refresh(application)
    return ApplicationRead.model_validate(application)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_application(
    application_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(analyst),
) -> None:
    application = await session.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    await _audit(session, user, "application.delete", application.id)
    await session.delete(application)
    await session.commit()
