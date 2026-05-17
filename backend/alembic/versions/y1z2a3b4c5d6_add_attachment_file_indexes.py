"""add attachment file indexes

Revision ID: y1z2a3b4c5d6
Revises: x9y8z7a6b5c4
Create Date: 2026-05-17

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "y1z2a3b4c5d6"
down_revision = "x9y8z7a6b5c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("attachment_files"):
        op.create_table(
            "attachment_files",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("content_id", sa.String(length=64), nullable=False),
            sa.Column("storage_key", sa.String(length=256), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("mime", sa.String(length=128), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("display_name", sa.String(length=240), nullable=False),
            sa.Column("derived_from_id", sa.String(length=64), nullable=True),
            sa.Column("derived_kind", sa.String(length=64), nullable=True),
            sa.Column("legacy_source", sa.String(length=512), nullable=True),
            sa.Column("storage_version", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "storage_key",
                name="uq_attachment_files_user_storage_key",
            ),
        )

    if not inspector.has_table("conversation_attachments"):
        op.create_table(
            "conversation_attachments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("conversation_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("attachment_file_id", sa.String(length=36), nullable=False),
            sa.Column("storage_key", sa.String(length=256), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["attachment_file_id"], ["attachment_files.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "conversation_id",
                "storage_key",
                name="uq_conversation_attachments_conversation_storage_key",
            ),
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_attachment_files_id ON attachment_files (id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_attachment_files_user_id ON attachment_files (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_attachment_files_content_id ON attachment_files (content_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_attachment_files_user_content ON attachment_files (user_id, content_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_attachment_files_created_at ON attachment_files (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversation_attachments_id ON conversation_attachments (id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversation_attachments_conversation_id ON conversation_attachments (conversation_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversation_attachments_user_id ON conversation_attachments (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversation_attachments_attachment_file_id ON conversation_attachments (attachment_file_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversation_attachments_user_conversation ON conversation_attachments (user_id, conversation_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversation_attachments_created_at ON conversation_attachments (created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conversation_attachments_created_at")
    op.execute("DROP INDEX IF EXISTS ix_conversation_attachments_user_conversation")
    op.execute("DROP INDEX IF EXISTS ix_conversation_attachments_attachment_file_id")
    op.execute("DROP INDEX IF EXISTS ix_conversation_attachments_user_id")
    op.execute("DROP INDEX IF EXISTS ix_conversation_attachments_conversation_id")
    op.execute("DROP INDEX IF EXISTS ix_conversation_attachments_id")
    op.execute("DROP INDEX IF EXISTS ix_attachment_files_created_at")
    op.execute("DROP INDEX IF EXISTS ix_attachment_files_user_content")
    op.execute("DROP INDEX IF EXISTS ix_attachment_files_content_id")
    op.execute("DROP INDEX IF EXISTS ix_attachment_files_user_id")
    op.execute("DROP INDEX IF EXISTS ix_attachment_files_id")
    op.execute("DROP TABLE IF EXISTS conversation_attachments")
    op.execute("DROP TABLE IF EXISTS attachment_files")
