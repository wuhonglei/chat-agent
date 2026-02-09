"""Mem0 替换：删除 user_profile_items 表，记忆改由 Mem0 管理

Revision ID: k7l8m9n0o1p2
Revises: 184aa73f173d
Create Date: 2026-02-09

"""

from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "k7l8m9n0o1p2"
down_revision = "184aa73f173d"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSION = 1024


def upgrade() -> None:
    op.drop_table("user_profile_items")


def downgrade() -> None:
    op.create_table(
        "user_profile_items",
        sa.Column("id", sa.VARCHAR(36), nullable=False),
        sa.Column("user_id", sa.VARCHAR(36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("type", sa.SmallInteger(), nullable=False),
        sa.Column(
            "embedding_vector",
            Vector(EMBEDDING_DIMENSION),
            nullable=True,
        ),
        sa.Column("embedding_model", sa.VARCHAR(50), nullable=True),
        sa.Column("text_normalized_hash", sa.VARCHAR(64), nullable=False),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("user_profile_items_pkey")),
    )
    op.create_index(
        "ix_user_profile_items_id",
        "user_profile_items",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_user_profile_items_user_id",
        "user_profile_items",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_profile_items_user_deleted",
        "user_profile_items",
        ["user_id", "deleted_at"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_user_profile_items_user_text_type",
        "user_profile_items",
        ["user_id", "text_normalized_hash", "type"],
    )
    op.create_foreign_key(
        "user_profile_items_user_id_fkey",
        "user_profile_items",
        "users",
        ["user_id"],
        ["id"],
    )
