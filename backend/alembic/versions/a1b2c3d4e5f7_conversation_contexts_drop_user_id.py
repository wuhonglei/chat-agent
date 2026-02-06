"""conversation_contexts 表去掉 user_id，主键改为仅 conversation_id

Revision ID: a1b2c3d4e5f7
Revises: e4b2c3d4e5f6
Create Date: 2026-02-07

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "e4b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 若存在 user_id 外键则先删除（建表若由 SQLModel 创建则会有）
    op.execute(
        sa.text(
            "ALTER TABLE conversation_contexts "
            "DROP CONSTRAINT IF EXISTS conversation_contexts_user_id_fkey"
        )
    )
    op.drop_constraint(
        "conversation_contexts_pkey",
        "conversation_contexts",
        type_="primary",
    )
    op.drop_column("conversation_contexts", "user_id")
    op.create_primary_key(
        "conversation_contexts_pkey",
        "conversation_contexts",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "conversation_contexts_pkey",
        "conversation_contexts",
        type_="primary",
    )
    op.add_column(
        "conversation_contexts",
        sa.Column("user_id", sa.VARCHAR(length=36), nullable=True),
    )
    # 从 conversations 回填 user_id
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE conversation_contexts SET user_id = "
            "(SELECT user_id FROM conversations WHERE conversations.id = conversation_contexts.conversation_id)"
        )
    )
    op.alter_column(
        "conversation_contexts",
        "user_id",
        existing_type=sa.VARCHAR(length=36),
        nullable=False,
    )
    op.create_primary_key(
        "conversation_contexts_pkey",
        "conversation_contexts",
        ["user_id", "conversation_id"],
    )
