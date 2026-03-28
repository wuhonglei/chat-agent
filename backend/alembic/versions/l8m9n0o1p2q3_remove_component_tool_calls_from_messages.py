"""remove component_tool_calls from messages

Revision ID: l8m9n0o1p2q3
Revises: k7l8m9n0o1p2
Create Date: 2026-03-28

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "l8m9n0o1p2q3"
down_revision = "k7l8m9n0o1p2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("messages", "component_tool_calls_duration")
    op.drop_column("messages", "component_tool_calls")


def downgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("component_tool_calls", sa.JSON(), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("component_tool_calls_duration", sa.Float(), nullable=True),
    )
