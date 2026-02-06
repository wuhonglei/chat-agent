"""用户画像语义检索：pgvector、messages 增加 query_embedding、user_profile_items 表、删除 user_profiles

Revision ID: d1e8f0a1b2c3
Revises: 60644bfb3542
Create Date: 2026-02-06

"""

from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision = "d1e8f0a1b2c3"
down_revision = "60644bfb3542"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSION = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "messages",
        sa.Column("query_embedding", Vector(EMBEDDING_DIMENSION), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("embedding_model", sa.String(64), nullable=True),
    )

    op.create_table(
        "user_profile_items",
        sa.Column("id", sa.VARCHAR(36), nullable=False),
        sa.Column("user_id", sa.VARCHAR(36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("type", sa.SmallInteger(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=True),
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
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("user_profile_items_pkey")),
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

    # 若存在 user_profiles 表则删除（旧数据不迁移，新表 user_profile_items 由归纳写入）
    op.drop_table("user_profiles", if_exists=True)


def downgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.VARCHAR(36), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("user_profiles_pkey")),
    )
    # 不回溯填充 user_profiles 数据，仅恢复空表
    op.drop_constraint(
        "uq_user_profile_items_user_text_type",
        "user_profile_items",
        type_="unique",
    )
    op.drop_index(
        "ix_user_profile_items_user_deleted",
        table_name="user_profile_items",
    )
    op.drop_index(
        "ix_user_profile_items_user_id",
        table_name="user_profile_items",
    )
    op.drop_table("user_profile_items")
    op.drop_column("messages", "embedding_model")
    op.drop_column("messages", "query_embedding")
    # 不 DROP EXTENSION vector，可能其他表仍在使用
    # op.execute("DROP EXTENSION IF EXISTS vector")
