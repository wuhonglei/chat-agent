"""messages.feedback 允许为 NULL

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-04-14

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "v2w3x4y5z6a7"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "messages",
        "feedback",
        existing_type=sa.JSON(),
        nullable=True,
    )


def downgrade() -> None:
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
    op.alter_column(
        "messages",
        "feedback",
        existing_type=sa.JSON(),
        nullable=False,
    )
