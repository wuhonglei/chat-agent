"""drop attachment legacy source

Revision ID: z2a3b4c5d6e7
Revises: y1z2a3b4c5d6
Create Date: 2026-05-17

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "z2a3b4c5d6e7"
down_revision = "y1z2a3b4c5d6"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )


def upgrade() -> None:
    if _has_column("attachment_files", "legacy_source"):
        op.drop_column("attachment_files", "legacy_source")


def downgrade() -> None:
    if not _has_column("attachment_files", "legacy_source"):
        op.add_column(
            "attachment_files",
            sa.Column("legacy_source", sa.String(length=512), nullable=True),
        )
