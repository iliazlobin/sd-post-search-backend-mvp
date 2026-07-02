"""Post service — CRUD, index status, soft delete."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from post_search.models.post import Post
from post_search.models.user import User
from post_search.schemas.post import (
    AuthorInfo,
    IndexStatusResponse,
    PostCreate,
    PostDetail,
    PostResponse,
)


class PostServiceError(Exception):
    """Base exception for post service errors."""


class AuthorNotFound(PostServiceError):
    """Raised when the author_id doesn't match any user."""


class PostNotFound(PostServiceError):
    """Raised when the post doesn't exist or is archived."""


class PostAlreadyArchived(PostServiceError):
    """Raised when attempting to delete an already-archived post."""


class PostService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_post(self, data: PostCreate) -> PostResponse:
        """Create a new post. Raises AuthorNotFound if author doesn't exist."""
        user = await self.session.get(User, data.author_id)
        if user is None:
            raise AuthorNotFound(f"user {data.author_id} not found")

        post = Post(
            author_id=data.author_id,
            text=data.text,
            language=data.language,
            privacy=data.privacy,
        )
        self.session.add(post)
        await self.session.flush()
        await self.session.refresh(post)
        await self.session.commit()

        return PostResponse(
            post_id=post.post_id,
            author_id=post.author_id,
            text=post.text,
            language=post.language,
            privacy=post.privacy,
            like_count=post.like_count,
            created_at=post.created_at,
        )

    async def get_post_detail(self, post_id: uuid.UUID) -> PostDetail:
        """Get post detail with author info. Raises PostNotFound if not found or archived."""
        result = await self.session.execute(
            select(Post, User)
            .join(User, Post.author_id == User.user_id)
            .where(Post.post_id == post_id, ~Post.is_archived)
        )
        row = result.one_or_none()
        if row is None:
            raise PostNotFound(f"post {post_id} not found")

        post, user = row
        return PostDetail(
            post_id=post.post_id,
            text=post.text,
            language=post.language,
            privacy=post.privacy,
            like_count=post.like_count,
            created_at=post.created_at,
            author=AuthorInfo(user_id=user.user_id, username=user.username),
        )

    async def get_index_status(self, post_id: uuid.UUID) -> IndexStatusResponse:
        """Check if a post is indexed. Always returns True for generated columns."""
        post = await self.session.get(Post, post_id)
        if post is None or post.is_archived:
            raise PostNotFound(f"post {post_id} not found")

        return IndexStatusResponse(
            indexed=True,
            indexed_at=post.created_at,
        )

    async def soft_delete_post(self, post_id: uuid.UUID) -> None:
        """Soft-delete a post by setting is_archived = True."""
        post = await self.session.get(Post, post_id)
        if post is None:
            raise PostNotFound(f"post {post_id} not found")
        if post.is_archived:
            raise PostAlreadyArchived(f"post {post_id} is already archived")

        post.is_archived = True
        await self.session.flush()
        await self.session.commit()
