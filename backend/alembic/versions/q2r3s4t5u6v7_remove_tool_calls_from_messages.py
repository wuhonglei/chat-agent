"""remove tool_calls from messages

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-04-04

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "q2r3s4t5u6v7"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("messages", "tool_calls")


def downgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("tool_calls", sa.JSON(), nullable=True),
    )
