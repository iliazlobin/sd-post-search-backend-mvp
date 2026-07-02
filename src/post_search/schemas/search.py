"""Search request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    author_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    language: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(
        ..., min_length=1, description="Search query (supports websearch syntax)"
    )
    mode: str = Field(default="lexical", pattern=r"^(lexical|semantic|hybrid)$")
    filters: SearchFilters | None = None
    page_size: int = Field(default=20, ge=1, le=100)
    page_token: str | None = None


class SearchResult(BaseModel):
    post_id: uuid.UUID
    author_id: uuid.UUID
    author_username: str
    text_snippet: str
    highlights: list[str]
    score: float
    created_at: datetime


class SearchResponse(BaseModel):
    results: list[SearchResult]
    next_page_token: str | None = None
