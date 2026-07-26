"""conversation_contexts 增加摘要失败计数与时间字段

Revision ID: d7e8f9a0b1c2
Revises: c5d6e7f8a9b0
Create Date: 2026-07-26

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d7e8f9a0b1c2"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_contexts",
        sa.Column(
            "summary_failure_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "conversation_contexts",
        sa.Column(
            "last_summary_failure_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("conversation_contexts", "last_summary_failure_at")
    op.drop_column("conversation_contexts", "summary_failure_count")
