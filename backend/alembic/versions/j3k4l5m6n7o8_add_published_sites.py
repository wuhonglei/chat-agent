"""添加 published_sites 表

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
Create Date: 2026-09-15
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "j3k4l5m6n7o8"
down_revision = "i2j3k4l5m6n7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("published_sites"):
        op.create_table(
            "published_sites",
            sa.Column("slug", sa.String(length=64), primary_key=True),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("conversation_id", sa.String(length=36), nullable=False),
            sa.Column("message_id", sa.String(length=36), nullable=True),
            sa.Column("site_root", sa.Text(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "entry",
                sa.String(length=128),
                nullable=False,
                server_default="index.html",
            ),
            sa.Column(
                "visibility",
                sa.String(length=16),
                nullable=False,
                server_default="unlisted",
            ),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("unpublished_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
            sa.UniqueConstraint("conversation_id"),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_published_sites_user_id "
        "ON published_sites (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_published_sites_unpublished_expires "
        "ON published_sites (unpublished_at, expires_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_published_sites_unpublished_expires")
    op.execute("DROP INDEX IF EXISTS ix_published_sites_user_id")
    op.drop_table("published_sites")
