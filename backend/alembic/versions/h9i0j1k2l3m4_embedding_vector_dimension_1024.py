"""将 embedding_vector 维度从 1536 改为 1024，与当前 embedding 模型输出一致

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-02-07

"""

from __future__ import annotations

from alembic import op

revision = "h9i0j1k2l3m4"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 先清空旧向量（1536 维无法直接转为 1024 维）
    op.execute("UPDATE user_profile_items SET embedding_vector = NULL")
    op.execute("UPDATE messages SET embedding_vector = NULL")

    op.execute(
        "ALTER TABLE user_profile_items "
        "ALTER COLUMN embedding_vector TYPE vector(1024)"
    )
    op.execute(
        "ALTER TABLE messages "
        "ALTER COLUMN embedding_vector TYPE vector(1024)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE user_profile_items "
        "ALTER COLUMN embedding_vector TYPE vector(1536)"
    )
    op.execute(
        "ALTER TABLE messages "
        "ALTER COLUMN embedding_vector TYPE vector(1536)"
    )
