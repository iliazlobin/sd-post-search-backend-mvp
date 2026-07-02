"""User service — create with uniqueness check."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from post_search.models.user import User
from post_search.schemas.user import UserCreate, UserResponse


class UserServiceError(Exception):
    """Base exception for user service errors."""


class UsernameTaken(UserServiceError):
    """Raised when the username is already in use."""


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_user(self, data: UserCreate) -> UserResponse:
        """Create a new user. Raises UsernameTaken if the username already exists."""
        existing = await self.session.execute(
            select(User).where(User.username == data.username)
        )
        if existing.scalar_one_or_none() is not None:
            raise UsernameTaken(f"username '{data.username}' already exists")

        user = User(username=data.username)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        await self.session.commit()

        return UserResponse(
            user_id=user.user_id,
            username=user.username,
            created_at=user.created_at,
        )
