"""White-box test fixtures — integration tests against a real test database."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Use a separate test database — set this before any post_search imports
# so that database.py's module-level engine construct picks up the right URL.
TEST_DATABASE_URL = (
    "postgresql+asyncpg://postsearch:postsearch@localhost:5432/postsearch_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from post_search.database import get_session  # noqa: E402
from post_search.main import create_app  # noqa: E402

CREATE_STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS pgcrypto",
    """CREATE TABLE IF NOT EXISTS users (
        user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        username varchar(50) UNIQUE NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS posts (
        post_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        author_id uuid NOT NULL REFERENCES users(user_id),
        text text NOT NULL,
        language varchar(5) NOT NULL DEFAULT 'en',
        created_at timestamptz NOT NULL DEFAULT now(),
        privacy varchar(20) NOT NULL DEFAULT 'public',
        like_count integer NOT NULL DEFAULT 0,
        is_archived boolean NOT NULL DEFAULT false,
        fts_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
        CONSTRAINT ck_post_language CHECK (language IN ('en', 'es', 'ja')),
        CONSTRAINT ck_post_privacy CHECK (privacy IN ('public', 'followers_only'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_posts_author_id ON posts (author_id)",
    "CREATE INDEX IF NOT EXISTS ix_posts_created_at ON posts (created_at)",
    "CREATE INDEX IF NOT EXISTS idx_posts_fts_vector ON posts USING gin (fts_vector)",
]


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test engine shared across the session. Tables created once."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    # Use raw DDL for proper PostgreSQL types (tsvector, GIN index)
    async with engine.begin() as conn:
        # Drop first to ensure clean slate
        await conn.execute(text("DROP TABLE IF EXISTS posts CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        for stmt in CREATE_STATEMENTS:
            await conn.execute(text(stmt))
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS posts CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
    await engine.dispose()


@pytest_asyncio.fixture
async def session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test database session with rollback isolation."""
    async_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as s:
        # Run within a transaction that we'll roll back
        await s.begin()
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI TestClient with injected DB session."""

    async def _get_session_override():
        yield session

    app = create_app()
    app.dependency_overrides[get_session] = _get_session_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def fresh_user(session: AsyncSession) -> dict:
    """Create a fresh user and return its data dict."""
    from post_search.schemas.user import UserCreate
    from post_search.services.user_service import UserService

    service = UserService(session)
    user = await service.create_user(
        UserCreate(username=f"test_{uuid.uuid4().hex[:8]}")
    )
    return {"user_id": user.user_id, "username": user.username}


@pytest_asyncio.fixture
async def fresh_post(session: AsyncSession, fresh_user: dict) -> dict:
    """Create a fresh post and return its data dict."""
    from post_search.schemas.post import PostCreate
    from post_search.services.post_service import PostService

    service = PostService(session)
    post = await service.create_post(
        PostCreate(
            author_id=fresh_user["user_id"],
            text="test post content for search testing",
        )
    )
    return {
        "post_id": post.post_id,
        "author_id": post.author_id,
        "text": post.text,
        "language": post.language,
        "privacy": post.privacy,
        "like_count": post.like_count,
        "created_at": post.created_at,
    }
