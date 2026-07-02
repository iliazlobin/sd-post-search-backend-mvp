"""Initial migration: create users, posts tables with fts_vector generated column and indexes.

Revision ID: 001
Revises: None
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgcrypto for gen_random_uuid()
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    # ── users ──────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── posts ──────────────────────────────────────────────
    op.create_table(
        "posts",
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            index=True,
        ),
        sa.Column("privacy", sa.String(20), nullable=False, server_default="public"),
        sa.Column("like_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default="false"),
        # Generated tsvector column — Postgres computes this on INSERT/UPDATE of text
        sa.Column(
            "fts_vector",
            postgresql.TSVECTOR,
            sa.Computed(
                "to_tsvector('english', text)",
                persisted=True,
            ),
            nullable=True,
        ),
        # Constraints
        sa.CheckConstraint("language IN ('en', 'es', 'ja')", name="ck_post_language"),
        sa.CheckConstraint(
            "privacy IN ('public', 'followers_only')", name="ck_post_privacy"
        ),
    )

    # ── GIN index on fts_vector for full-text search ───────
    op.create_index(
        "idx_posts_fts_vector", "posts", ["fts_vector"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("idx_posts_fts_vector", table_name="posts")
    op.drop_table("posts")
    op.drop_table("users")
