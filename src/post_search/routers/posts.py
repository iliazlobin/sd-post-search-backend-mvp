"""Posts router — CRUD, index-status, soft delete.

POST   /api/v1/posts                     → create
GET    /api/v1/posts/{post_id}           → detail
GET    /api/v1/posts/{post_id}/index-status → check index
DELETE /api/v1/posts/{post_id}           → soft delete
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from post_search.database import get_session
from post_search.schemas.post import (
    IndexStatusResponse,
    PostCreate,
    PostDetail,
    PostResponse,
)
from post_search.services.post_service import (
    AuthorNotFound,
    PostAlreadyArchived,
    PostNotFound,
    PostService,
)

router = APIRouter(prefix="/api/v1/posts", tags=["posts"])


def _not_found(detail: str):
    from fastapi import HTTPException

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PostResponse)
async def create_post(data: PostCreate, session: AsyncSession = Depends(get_session)):
    """Create a new post. Author must exist."""
    service = PostService(session)
    try:
        return await service.create_post(data)
    except AuthorNotFound as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{post_id}", response_model=PostDetail)
async def get_post(post_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Get post detail with author info."""
    service = PostService(session)
    try:
        return await service.get_post_detail(post_id)
    except PostNotFound as exc:
        raise _not_found(str(exc))


@router.get("/{post_id}/index-status", response_model=IndexStatusResponse)
async def get_index_status(
    post_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    """Check whether a post is indexed (always True for generated tsvector)."""
    service = PostService(session)
    try:
        return await service.get_index_status(post_id)
    except PostNotFound as exc:
        raise _not_found(str(exc))


@router.delete("/{post_id}", response_model=dict)
async def delete_post(post_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Soft-delete a post."""
    service = PostService(session)
    try:
        await service.soft_delete_post(post_id)
        return {"status": "archived"}
    except PostNotFound as exc:
        raise _not_found(str(exc))
    except PostAlreadyArchived as exc:
        raise _not_found(str(exc))
