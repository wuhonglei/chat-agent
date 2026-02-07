"""refactor: 移除 conversation_contexts.recent_summary 列

Revision ID: 184aa73f173d
Revises: j6k7l8m9n0o1
Create Date: 2026-02-07 15:31:46.937976

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "184aa73f173d"
down_revision = "j6k7l8m9n0o1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE conversation_contexts
        SET summary_before_window = recent_summary
        WHERE summary_before_window IS NULL AND recent_summary IS NOT NULL
        """
    )
    op.drop_column("conversation_contexts", "recent_summary")


def downgrade() -> None:
    op.add_column(
        "conversation_contexts",
        sa.Column("recent_summary", sa.VARCHAR(), nullable=True),
    )
