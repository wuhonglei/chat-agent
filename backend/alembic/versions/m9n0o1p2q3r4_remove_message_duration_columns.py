"""remove message duration columns from messages

Revision ID: m9n0o1p2q3r4
Revises: l8m9n0o1p2q3
Create Date: 2026-03-29

"""

from __future__ import annotations

from alembic import op

revision = "m9n0o1p2q3r4"
down_revision = "l8m9n0o1p2q3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("messages", "total_duration")
    op.drop_column("messages", "content_duration")
    op.drop_column("messages", "reasoning_duration")
    op.drop_column("messages", "tool_calls_duration")


def downgrade() -> None:
    pass
