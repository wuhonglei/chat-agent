"""将 embedding_vector 维度从 1536 改为 1024，与当前 embedding 模型输出一致

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-02-07

"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector

from alembic import op

revision = "h9i0j1k2l3m4"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None

NEW_DIM = 1024


def upgrade() -> None:
    # 先清空旧向量（1536 维无法直接转为 1024 维）
    op.execute("UPDATE user_profile_items SET embedding_vector = NULL")
    op.execute("UPDATE messages SET embedding_vector = NULL")

    op.alter_column(
        "user_profile_items",
        "embedding_vector",
        existing_type=Vector(1536),
        type_=Vector(NEW_DIM),
        existing_nullable=True,
    )
    op.alter_column(
        "messages",
        "embedding_vector",
        existing_type=Vector(1536),
        type_=Vector(NEW_DIM),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "user_profile_items",
        "embedding_vector",
        existing_type=Vector(NEW_DIM),
        type_=Vector(1536),
        existing_nullable=True,
    )
    op.alter_column(
        "messages",
        "embedding_vector",
        existing_type=Vector(NEW_DIM),
        type_=Vector(1536),
        existing_nullable=True,
    )
