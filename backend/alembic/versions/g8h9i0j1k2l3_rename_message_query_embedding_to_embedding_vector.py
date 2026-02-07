"""将 messages 表字段 query_embedding 重命名为 embedding_vector

Revision ID: g8h9i0j1k2l3
Revises: a1b2c3d4e5f7
Create Date: 2026-02-07

"""

from __future__ import annotations

from alembic import op

revision = "g8h9i0j1k2l3"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "messages",
        "query_embedding",
        new_column_name="embedding_vector",
    )


def downgrade() -> None:
    op.alter_column(
        "messages",
        "embedding_vector",
        new_column_name="query_embedding",
    )
