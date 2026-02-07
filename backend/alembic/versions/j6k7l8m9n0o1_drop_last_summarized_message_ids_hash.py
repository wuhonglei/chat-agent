"""移除 conversation_contexts.last_summarized_message_ids_hash 列

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-02-07

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel  # noqa

from alembic import op

# revision identifiers, used by Alembic.
revision = "j6k7l8m9n0o1"
down_revision = "i5j6k7l8m9n0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("conversation_contexts", "last_summarized_message_ids_hash")


def downgrade() -> None:
    op.add_column(
        "conversation_contexts",
        sa.Column("last_summarized_message_ids_hash", sa.VARCHAR(64), nullable=True),
    )
