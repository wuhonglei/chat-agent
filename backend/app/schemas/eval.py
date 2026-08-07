"""评估相关 Pydantic 模型"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

# ── 枚举 ──


class BadCaseSource(str, Enum):
    """入队来源"""

    RULE_FAIL = "rule_fail"
    LOW_SCORE = "low_score"
    THUMB_DOWN = "thumb_down"


class BadCaseStatus(str, Enum):
    """复核状态"""

    PENDING = "pending"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class BadCaseAttribution(str, Enum):
    """归因分类"""

    RETRIEVAL_MISS = "retrieval_miss"
    TOOL_FAILURE = "tool_failure"
    MODEL_CAPABILITY = "model_capability"
    CONTEXT_LOSS = "context_loss"
    ANNOTATION_ISSUE = "annotation_issue"
    HALLUCINATION = "hallucination"
    OTHER = "other"


class BadCaseResolution(str, Enum):
    """处理方式"""

    ADDED_TO_DATASET = "added_to_dataset"
    PROMPT_FIX = "prompt_fix"
    MODEL_UPGRADE = "model_upgrade"
    ANNOTATION_FIXED = "annotation_fixed"
    NO_ACTION = "no_action"


# ── 请求 ──


class BadCaseUpdateRequest(BaseModel):
    """更新 bad case（人工归因）"""

    status: BadCaseStatus | None = None
    attribution: BadCaseAttribution | None = None
    reviewer_notes: str | None = None
    resolution: BadCaseResolution | None = None


# ── 响应 ──


class BadCaseItemResponse(BaseModel):
    """Bad case 条目响应"""

    id: str
    source: BadCaseSource
    message_id: str | None
    conversation_id: str | None
    user_id: str | None
    query: str
    answer: str
    rule_scores: dict[str, Any]
    judge_scores: dict[str, Any] | None
    trace_id: str | None
    feedback_reasons: list[str]
    feedback_comment: str | None
    status: BadCaseStatus
    attribution: BadCaseAttribution | None
    reviewer_notes: str | None
    resolution: BadCaseResolution | None
    created_at: datetime
    reviewed_at: datetime | None
    resolved_at: datetime | None


class BadCaseListResponse(BaseModel):
    """Bad case 列表响应"""

    items: list[BadCaseItemResponse]
    total: int
    page: int
    page_size: int


class BadCaseStatsResponse(BaseModel):
    """Bad case 统计"""

    total: int
    by_status: dict[str, int]
    by_source: dict[str, int]
    by_attribution: dict[str, int]


class EvalRunLogResponse(BaseModel):
    """评估运行日志响应"""

    id: str
    run_type: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    total_traces: int
    after_dedup: int
    candidate_pool: int
    sampled_count: int
    sample_breakdown: dict[str, Any]
    judge_success: int
    judge_failed: int
    low_score_count: int
    error_message: str | None
