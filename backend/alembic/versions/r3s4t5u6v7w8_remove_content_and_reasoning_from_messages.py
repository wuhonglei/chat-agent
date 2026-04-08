"""remove content and reasoning from messages

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-04-04

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "r3s4t5u6v7w8"
down_revision = "q2r3s4t5u6v7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("messages", "content")
    op.drop_column("messages", "reasoning")


def downgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "messages",
        sa.Column("reasoning", sa.Text(), nullable=True),
    )
