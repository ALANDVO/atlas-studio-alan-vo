"""SQLAlchemy async database setup."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_session() -> AsyncSession:
    """FastAPI dependency providing a database session."""
    async with AsyncSessionFactory() as session:
        yield session


async def init_db() -> None:
    """Create all tables (for development / tests)."""
    from ..models.orm import Posting, ScoringRun, AuditLog, LabelingExample  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)