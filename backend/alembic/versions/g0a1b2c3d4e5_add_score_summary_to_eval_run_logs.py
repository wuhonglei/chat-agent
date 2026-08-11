"""eval_run_logs 增加 score_summary

Revision ID: g0a1b2c3d4e5
Revises: f9a0b1c2d3e4
Create Date: 2026-08-11
"""

import sqlalchemy as sa
from sqlalchemy import JSON

from alembic import op

revision = "g0a1b2c3d4e5"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "eval_run_logs",
        sa.Column("score_summary", JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("eval_run_logs", "score_summary")
