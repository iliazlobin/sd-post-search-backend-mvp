"""Users router — POST /api/v1/users."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from post_search.database import get_session
from post_search.schemas.user import UserCreate, UserResponse
from post_search.services.user_service import UsernameTaken, UserService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(data: UserCreate, session: AsyncSession = Depends(get_session)):
    """Create a new user with a unique username."""
    service = UserService(session)
    try:
        return await service.create_user(data)
    except UsernameTaken as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
