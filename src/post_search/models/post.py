"""Post ORM model with generated tsvector column and GIN FTS index."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from post_search.database import Base


class Post(Base):
    __tablename__ = "posts"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(
        String(5), nullable=False, server_default="en"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    privacy: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="public"
    )
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Generated tsvector column — Postgres computes this on INSERT/UPDATE of text.
    # Defined in the Alembic migration as:
    #   fts_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
    # The ORM maps it as read-only; we never set it from Python.
    fts_vector: Mapped[str | None] = mapped_column(
        "fts_vector", deferred=True, insert_default=None
    )

    author = relationship("User", back_populates="posts", lazy="selectin")

    __table_args__ = (
        # Language must be one of the supported values
        CheckConstraint("language IN ('en', 'es', 'ja')", name="ck_post_language"),
        # Privacy must be one of the allowed values
        CheckConstraint(
            "privacy IN ('public', 'followers_only')", name="ck_post_privacy"
        ),
    )
