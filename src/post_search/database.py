"""Async database engine, session factory, and FastAPI dependency.

Provides a single async SQLAlchemy engine backed by asyncpg and a
`get_session` async generator for use with FastAPI's Depends.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from post_search.config import settings

engine = create_async_engine(
    settings.database_url, echo=False, pool_size=5, max_overflow=10
)
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session.

    Usage:
        @router.get("/...")
        async def handler(session: Annotated[AsyncSession, Depends(get_session)]):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
