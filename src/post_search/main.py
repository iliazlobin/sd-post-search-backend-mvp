"""FastAPI app factory — create_app() with lifespan and /healthz.

The app factory pattern keeps testability clean: white-box tests can import
create_app() and use TestClient without module-level side effects.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from post_search.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — runs startup/shutdown logic."""
    # Startup: engine is already created; no explicit connect needed.
    # Alembic runs upgrade head as a separate step before the app starts.
    yield
    # Shutdown: dispose the engine
    await engine.dispose()


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="Post Search MVP",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Register routers
    from post_search.routers import health, posts, search, users

    app.include_router(health.router)
    app.include_router(users.router)
    app.include_router(posts.router)
    app.include_router(search.router)

    return app


app = create_app()
