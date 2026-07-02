"""User request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(
        ..., min_length=1, max_length=50, description="Display name, must be unique"
    )


class UserResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    created_at: datetime
