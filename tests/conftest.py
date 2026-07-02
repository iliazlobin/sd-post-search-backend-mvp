"""White-box test fixtures — integration tests against a real test database."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Use a separate test database — set this before any post_search imports
# so that database.py's module-level engine construct picks up the right URL.
TEST_DATABASE_URL = (
    "postgresql+asyncpg://postsearch:postsearch@localhost:5432/postsearch_test"
)
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)

from post_search.database import Base, get_session  # noqa: E402
from post_search.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async fixtures."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test engine shared across the session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    # Create all tables (use metadata.create_all since we manage schema in tests)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
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
