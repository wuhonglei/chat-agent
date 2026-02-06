"""add_user_profiles_and_user_contexts_tables

Revision ID: 60644bfb3542
Revises: ba2310dcb4e9
Create Date: 2026-02-04 22:10:20.519508

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "60644bfb3542"
down_revision = "ba2310dcb4e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.VARCHAR(length=36), nullable=False),
        sa.Column("facts", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("preferences", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("user_profiles_pkey")),
        if_not_exists=True,
    )

    op.create_table(
        "user_contexts",
        sa.Column("user_id", sa.VARCHAR(length=36), nullable=False),
        sa.Column("conversation_id", sa.VARCHAR(length=36), nullable=False),
        sa.Column("summary_before_window", sa.VARCHAR(), nullable=True),
        sa.Column("recent_summary", sa.VARCHAR(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "conversation_id", name=op.f("user_contexts_pkey")
        ),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
    op.drop_table("user_contexts")
