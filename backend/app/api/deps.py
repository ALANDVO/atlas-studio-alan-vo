"""FastAPI dependencies: database, auth, lifecycle."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..core.security import CurrentUser, get_current_user, require_role, Role
from ..services.lifecycle import PostingLifecycle, ScoringConfig, default_fetch
from ..services.scorer import TFIDFScorer

# Re-export for convenience.
viewer = require_role(Role.viewer)
analyst = require_role(Role.analyst)
admin = require_role(Role.admin)

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


async def get_lifecycle(
    session: AsyncSession = Depends(get_session),
) -> PostingLifecycle:
    """Create a PostingLifecycle instance bound to the request session."""
    config = ScoringConfig()
    return PostingLifecycle(
        session=session,
        config=config,
        fetch_fn=default_fetch,
    )


async def get_scorer() -> TFIDFScorer:
    """Provide a default scorer (not fitted — call fit() before use)."""
    return TFIDFScorer(ScoringConfig())