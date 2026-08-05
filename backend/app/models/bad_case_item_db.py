"""低分复核队列模型：自动收集规则评估失败、裁判低分、用户点踩的样本。"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON as SQLJSON
from sqlalchemy import Column, DateTime, String, Text
from sqlmodel import Field, SQLModel

from app.utils.common import gen_uuid
from app.utils.date import get_datetime_now


class BadCaseItemDb(SQLModel, table=True):
    """低分复核队列条目"""

    __tablename__ = "bad_case_items"  # pyright: ignore[reportAssignmentType]

    id: str = Field(
        default_factory=gen_uuid, primary_key=True, index=True, max_length=36
    )

    # ── 来源 ──
    source: str = Field(
        max_length=32,
        description="入队来源: rule_fail / low_score / thumb_down",
    )
    message_id: str | None = Field(
        default=None,
        sa_column=Column(String(36), index=True),
        description="关联的助手消息 ID",
    )
    conversation_id: str | None = Field(
        default=None,
        sa_column=Column(String(36), index=True),
        description="关联的对话 ID",
    )
    user_id: str | None = Field(
        default=None,
        sa_column=Column(String(36), index=True),
        description="关联的用户 ID",
    )

    # ── 评估数据快照 ──
    query: str = Field(
        default="", sa_column=Column(Text), description="用户原始问题（截取前 500 字）"
    )
    answer: str = Field(
        default="", sa_column=Column(Text), description="模型回答（截取前 1000 字）"
    )
    rule_scores: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=SQLJSON,
        description="规则评估器分数快照 (valid_answer, tool_whitelist_ok, tool_call_count 等)",
    )
    judge_scores: dict[str, Any] | None = Field(
        default=None,
        sa_type=SQLJSON,
        description="裁判模型分数 (correctness, completeness)",
    )
    trace_id: str | None = Field(
        default=None, max_length=64, description="Langfuse trace ID"
    )

    # ── 用户反馈（thumb_down 来源时填充）──
    feedback_reasons: list[str] = Field(
        default_factory=list,
        sa_type=SQLJSON,
        description="用户点踩原因标签列表",
    )
    feedback_comment: str | None = Field(
        default=None, sa_column=Column(Text), description="用户点踩自由文本"
    )

    # ── 状态 ──
    status: str = Field(
        default="pending",
        max_length=16,
        description="复核状态: pending / reviewing / resolved / dismissed",
    )

    # ── 人工归因 ──
    attribution: str | None = Field(
        default=None,
        max_length=32,
        description=(
            "归因分类: retrieval_miss / tool_failure / model_capability / "
            "context_loss / annotation_issue / hallucination / other"
        ),
    )
    reviewer_notes: str | None = Field(
        default=None, sa_column=Column(Text), description="复核人备注"
    )
    resolution: str | None = Field(
        default=None,
        max_length=32,
        description=(
            "处理方式: added_to_dataset / prompt_fix / model_upgrade / "
            "annotation_fixed / no_action"
        ),
    )

    # ── 时间戳 ──
    created_at: datetime = Field(
        default_factory=lambda: get_datetime_now(),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    reviewed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
        description="开始复核时间",
    )
    resolved_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
        description="解决时间",
    )
