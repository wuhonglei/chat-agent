"""评估运行日志：记录每次定时/手动评估的执行情况。"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON as SQLJSON
from sqlalchemy import Column, DateTime, Integer, Text
from sqlmodel import Field, SQLModel

from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now


class EvalRunLog(SQLModel, table=True):
    """每次评估运行的统计记录"""

    __tablename__ = "eval_run_logs"  # pyright: ignore[reportAssignmentType]

    id: str = Field(
        default_factory=gen_uuid, primary_key=True, index=True, max_length=36
    )
    run_type: str = Field(
        max_length=32,
        default="scheduled",
        description="运行类型: scheduled(定时) / manual(手动触发)",
    )
    started_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    status: str = Field(
        default="running",
        max_length=16,
        description="运行状态: running / success / failed",
    )

    # ── 采样统计 ──
    total_traces: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    after_dedup: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    candidate_pool: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    sampled_count: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    sample_breakdown: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=SQLJSON,
        description="分层采样明细: {special: N, high: N, medium: N, low: N}",
    )

    # ── 裁判统计 ──
    judge_success: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    judge_failed: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    low_score_count: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )

    # ── 错误信息 ──
    error_message: str | None = Field(
        default=None, sa_column=Column(Text), description="运行失败时的错误信息"
    )

    created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
