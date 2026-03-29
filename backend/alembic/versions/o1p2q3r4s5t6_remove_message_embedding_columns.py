"""remove embedding_vector and embedding_model from messages

Revision ID: o1p2q3r4s5t6
Revises: n0o1p2q3r4s5
Create Date: 2026-03-29

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel  # noqa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "o1p2q3r4s5t6"
down_revision = "n0o1p2q3r4s5"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSION = 1024


def upgrade() -> None:
    op.drop_column("messages", "embedding_vector")
    op.drop_column("messages", "embedding_model")


def downgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "embedding_vector",
            Vector(EMBEDDING_DIMENSION),
            nullable=True,
        ),
    )
    op.add_column(
        "messages",
        sa.Column("embedding_model", sa.String(length=64), nullable=True),
    )
