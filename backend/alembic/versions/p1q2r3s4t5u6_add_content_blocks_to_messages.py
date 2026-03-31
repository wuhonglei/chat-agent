"""add content_blocks to messages

Revision ID: p1q2r3s4t5u6
Revises: o1p2q3r4s5t6
Create Date: 2026-03-30

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel  # noqa

from alembic import op

revision = "p1q2r3s4t5u6"
down_revision = "o1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("content_blocks", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "content_blocks")
