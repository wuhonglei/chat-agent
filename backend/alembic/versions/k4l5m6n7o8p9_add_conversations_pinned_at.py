"""conversations 表增加 pinned_at 字段

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
Create Date: 2026-09-28

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "k4l5m6n7o8p9"
down_revision = "j3k4l5m6n7o8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_conversations_user_active_pinned
        ON conversations (user_id, is_active, pinned_at DESC, id DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conversations_user_active_pinned")
    op.drop_column("conversations", "pinned_at")
