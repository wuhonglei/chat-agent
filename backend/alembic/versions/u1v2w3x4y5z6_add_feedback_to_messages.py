"""add feedback field to messages

Revision ID: u1v2w3x4y5z6
Revises: s4t5u6v7w8x9
Create Date: 2026-04-14

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "u1v2w3x4y5z6"
down_revision = "s4t5u6v7w8x9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("feedback", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE messages
        SET feedback = json_build_object(
            'value', 'default',
            'updated_at', NULL
        )
        WHERE feedback IS NULL
        """
    )
    op.alter_column("messages", "feedback", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    op.drop_column("messages", "feedback")
