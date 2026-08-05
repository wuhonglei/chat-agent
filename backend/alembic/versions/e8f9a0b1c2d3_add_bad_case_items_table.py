"""添加低分复核队列表 bad_case_items

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from sqlalchemy import JSON

from alembic import op

# revision identifiers
revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bad_case_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False, index=True),
        sa.Column("message_id", sa.String(36), nullable=True, index=True),
        sa.Column("conversation_id", sa.String(36), nullable=True, index=True),
        sa.Column("user_id", sa.String(36), nullable=True, index=True),
        sa.Column("query", sa.Text, nullable=False, server_default=""),
        sa.Column("answer", sa.Text, nullable=False, server_default=""),
        sa.Column("rule_scores", JSON, nullable=False, server_default="{}"),
        sa.Column("judge_scores", JSON, nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("feedback_reasons", JSON, nullable=False, server_default="[]"),
        sa.Column("feedback_comment", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("attribution", sa.String(32), nullable=True, index=True),
        sa.Column("reviewer_notes", sa.Text, nullable=True),
        sa.Column("resolution", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("bad_case_items")
