"""添加评估运行日志表 eval_run_logs

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-08-06
"""

import sqlalchemy as sa
from sqlalchemy import JSON

from alembic import op

revision = "f9a0b1c2d3e4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_run_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_type",
            sa.String(32),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="running",
        ),
        sa.Column("total_traces", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("after_dedup", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_pool", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sampled_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sample_breakdown", JSON, nullable=False, server_default="{}"),
        sa.Column("judge_success", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("judge_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("low_score_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eval_run_logs_id", "eval_run_logs", ["id"])


def downgrade() -> None:
    op.drop_index("ix_eval_run_logs_id", table_name="eval_run_logs")
    op.drop_table("eval_run_logs")
