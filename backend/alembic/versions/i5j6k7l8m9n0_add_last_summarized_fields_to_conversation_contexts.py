"""为 conversation_contexts 增加 last_summarized_message_ids_hash 与 last_summarized_message_ids

Revision ID: i5j6k7l8m9n0
Revises: 667cf79bd836
Create Date: 2026-02-07

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel  # noqa

from alembic import op

# revision identifiers, used by Alembic.
revision = "i5j6k7l8m9n0"
down_revision = "667cf79bd836"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_contexts",
        sa.Column("last_summarized_message_ids_hash", sa.VARCHAR(64), nullable=True),
    )
    op.add_column(
        "conversation_contexts",
        sa.Column("last_summarized_message_ids", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversation_contexts", "last_summarized_message_ids")
    op.drop_column("conversation_contexts", "last_summarized_message_ids_hash")
