"""Search router — POST /api/v1/search."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from post_search.database import get_session
from post_search.schemas.search import SearchRequest, SearchResponse
from post_search.services.search_service import (
    InvalidPageToken,
    SearchService,
    UnsupportedMode,
)

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(data: SearchRequest, session: AsyncSession = Depends(get_session)):
    """Full-text search over posts with filtering, pagination, and highlighting."""
    service = SearchService(session)
    try:
        return await service.search(data)
    except UnsupportedMode as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        )
    except InvalidPageToken as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
