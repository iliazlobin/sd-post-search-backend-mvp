"""Post request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    author_id: uuid.UUID
    text: str = Field(..., min_length=1, description="Post body text")
    language: str = Field(
        default="en", pattern=r"^(en|es|ja)$", description="Language code"
    )
    privacy: str = Field(
        default="public",
        pattern=r"^(public|followers_only)$",
        description="Privacy level",
    )


class PostResponse(BaseModel):
    post_id: uuid.UUID
    author_id: uuid.UUID
    text: str
    language: str
    privacy: str
    like_count: int
    created_at: datetime


class AuthorInfo(BaseModel):
    user_id: uuid.UUID
    username: str


class PostDetail(BaseModel):
    post_id: uuid.UUID
    text: str
    language: str
    privacy: str
    like_count: int
    created_at: datetime
    author: AuthorInfo


class IndexStatusResponse(BaseModel):
    indexed: bool
    indexed_at: datetime
