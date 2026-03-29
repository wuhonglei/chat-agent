"""remove token_stats column from messages

Revision ID: n0o1p2q3r4s5
Revises: m9n0o1p2q3r4
Create Date: 2026-03-29

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel  # noqa

from alembic import op

revision = "n0o1p2q3r4s5"
down_revision = "m9n0o1p2q3r4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("messages", "token_stats")


def downgrade() -> None:
    op.add_column("messages", sa.Column("token_stats", sa.JSON(), nullable=True))
