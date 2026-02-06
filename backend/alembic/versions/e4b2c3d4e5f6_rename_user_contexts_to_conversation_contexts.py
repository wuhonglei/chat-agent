"""rename user_contexts to conversation_contexts

Revision ID: e4b2c3d4e5f6
Revises: d1e8f0a1b2c3
Create Date: 2026-02-07

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "e4b2c3d4e5f6"
down_revision = "d1e8f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("user_contexts", "conversation_contexts")


def downgrade() -> None:
    op.rename_table("conversation_contexts", "user_contexts")
