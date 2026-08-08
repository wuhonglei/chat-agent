"""分层采样器：从 Langfuse Trace 中按风险等级和特殊信号分层抽样。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.mcp.constants import (
    CONTEXT7_SERVER,
    EDIT_FILE_LLM,
    EXECUTE_CODE_LLM,
    SHELL_LLM,
    TAVILY_SERVER,
    WEB_PAGES_EXTRACT_LLM,
    WEB_SEARCH_LLM,
    WEB_SITE_CRAWL_BARE,
    WRITE_FILE_LLM,
)
from app.mcp.tool_naming import llm_tool_name
from app.schemas.config import EvalWorkerConfig
from app.utils.logger import logger


class RiskLevel(str, Enum):
    HIGH = "high"  # code_execute_code, file_write_file, shell_exec
    MEDIUM = "medium"  # tavily_*, context7_*
    LOW = "low"  # 纯模型生成


# 高风险工具: 出错代价大（代码执行、文件写改、Shell）— 与 mcp.constants LLM 名对齐
HIGH_RISK_TOOLS = {
    EXECUTE_CODE_LLM,
    WRITE_FILE_LLM,
    EDIT_FILE_LLM,
    SHELL_LLM,
}

# 中风险工具: 检索类，可能返回不相关内容
MED_RISK_TOOLS = {
    WEB_SEARCH_LLM,
    WEB_PAGES_EXTRACT_LLM,
    llm_tool_name(TAVILY_SERVER, WEB_SITE_CRAWL_BARE),
    llm_tool_name(CONTEXT7_SERVER, "resolve-library-id"),
    llm_tool_name(CONTEXT7_SERVER, "query-docs"),
}


def sample_rates_from_config(
    cfg: EvalWorkerConfig | None = None,
) -> dict[RiskLevel, float]:
    """从 EvalWorkerConfig 读取分层采样比例（唯一默认源）。"""
    c = cfg or EvalWorkerConfig()
    return {
        RiskLevel.HIGH: c.sample_rate_high,
        RiskLevel.MEDIUM: c.sample_rate_medium,
        RiskLevel.LOW: c.sample_rate_low,
    }


@dataclass
class SampleResult:
    """采样结果"""

    traces: list[dict[str, Any]] = field(default_factory=list)
    breakdown: dict[str, int] = field(default_factory=dict)
    skipped_dedup: int = 0
    skipped_rule_filter: int = 0


def _score_map(trace: dict[str, Any]) -> dict[str, Any]:
    scores = trace.get("scores") or []
    if not isinstance(scores, list):
        return {}
    result: dict[str, Any] = {}
    for s in scores:
        if isinstance(s, dict) and s.get("name"):
            result[str(s["name"])] = s.get("value")
    return result


def _trace_metadata(trace: dict[str, Any]) -> dict[str, Any]:
    meta = trace.get("metadata") or {}
    return meta if isinstance(meta, dict) else {}


def _trace_output_text(trace: dict[str, Any]) -> str:
    output = trace.get("output", "")
    if isinstance(output, str):
        return output
    if output is None:
        return ""
    return str(output)


def _called_tools(trace: dict[str, Any]) -> set[str]:
    meta = _trace_metadata(trace)
    raw = meta.get("called_tools")
    if isinstance(raw, list):
        return {str(name) for name in raw if name}
    if isinstance(raw, str) and raw:
        return {raw}
    return set()


def classify_risk(trace: dict[str, Any]) -> RiskLevel:
    """根据 Trace 中的工具调用判断风险等级。"""
    tool_names = _called_tools(trace)

    if not tool_names:
        score_map = _score_map(trace)
        tool_count = score_map.get("tool_call_count", 0) or 0
        try:
            tool_count_n = int(tool_count)
        except (TypeError, ValueError):
            tool_count_n = 0
        if tool_count_n > 0:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    # 子串匹配：兼容带 server 前缀的工具名
    lowered = {name.lower() for name in tool_names}
    for high in HIGH_RISK_TOOLS:
        if any(high in name or name.endswith(high) for name in lowered):
            return RiskLevel.HIGH
    for med in MED_RISK_TOOLS:
        if any(med in name or name.endswith(med) for name in lowered):
            return RiskLevel.MEDIUM

    # 有工具但不在名单：按中风险
    return RiskLevel.MEDIUM


def is_effective_answer(trace: dict[str, Any]) -> bool:
    """规则预筛: 判断是否为有效回答（排除空回答/极短/闲聊）。"""
    score_map = _score_map(trace)

    if score_map.get("valid_answer") is False:
        return False

    output = _trace_output_text(trace)
    if len(output.strip()) < 10:
        return False

    tool_count = score_map.get("tool_call_count", 0) or 0
    try:
        tool_count_n = int(tool_count)
    except (TypeError, ValueError):
        tool_count_n = 0
    if tool_count_n == 0 and len(output.strip()) < 50:
        return False

    return True


def detect_special_signals(
    trace: dict[str, Any],
    *,
    follow_up_trace_ids: set[str] | None = None,
    thumb_down_message_ids: set[str] | None = None,
    high_latency_threshold_s: float | None = None,
) -> bool:
    """检测特殊场景信号（100% 采样）。方案 A：点踩 / 快速追问 / 高延迟。"""
    follow_up_trace_ids = follow_up_trace_ids or set()
    thumb_down_message_ids = thumb_down_message_ids or set()
    if high_latency_threshold_s is None:
        high_latency_threshold_s = EvalWorkerConfig().high_latency_threshold_s

    meta = _trace_metadata(trace)
    message_id = str(meta.get("assistant_message_id") or meta.get("message_id") or "")
    if message_id and message_id in thumb_down_message_ids:
        return True

    trace_id = str(trace.get("id") or "")
    if trace_id and trace_id in follow_up_trace_ids:
        return True

    latency = trace.get("latency", 0) or 0
    try:
        latency_n = float(latency)
    except (TypeError, ValueError):
        latency_n = 0.0
    if latency_n > high_latency_threshold_s:
        return True

    return False


def stratified_sample(
    traces: list[dict[str, Any]],
    *,
    follow_up_trace_ids: set[str] | None = None,
    thumb_down_message_ids: set[str] | None = None,
    sample_rates: dict[RiskLevel, float] | None = None,
    high_latency_threshold_s: float | None = None,
    seed: int = 42,
) -> SampleResult:
    """分层采样入口。采样比例/高延迟阈值默认来自 EvalWorkerConfig。"""
    rng = random.Random(seed)
    defaults = sample_rates_from_config()
    rates = {**defaults, **(sample_rates or {})}
    if high_latency_threshold_s is None:
        high_latency_threshold_s = EvalWorkerConfig().high_latency_threshold_s
    result = SampleResult()

    valid_traces: list[dict[str, Any]] = []
    for t in traces:
        output = _trace_output_text(t)
        if not output.strip():
            result.skipped_rule_filter += 1
            continue
        valid_traces.append(t)

    logger.info(
        "Sampler: filtered empty output",
        total=len(traces),
        valid=len(valid_traces),
        skipped=len(traces) - len(valid_traces),
    )

    special_bucket: list[dict[str, Any]] = []
    risk_buckets: dict[RiskLevel, list[dict[str, Any]]] = {
        RiskLevel.HIGH: [],
        RiskLevel.MEDIUM: [],
        RiskLevel.LOW: [],
    }

    for t in valid_traces:
        if not is_effective_answer(t):
            result.skipped_rule_filter += 1
            continue

        if detect_special_signals(
            t,
            follow_up_trace_ids=follow_up_trace_ids,
            thumb_down_message_ids=thumb_down_message_ids,
            high_latency_threshold_s=high_latency_threshold_s,
        ):
            special_bucket.append(t)
            continue

        risk = classify_risk(t)
        risk_buckets[risk].append(t)

    sampled = list(special_bucket)
    result.breakdown["special"] = len(special_bucket)

    for risk_level, bucket in risk_buckets.items():
        rate = rates[risk_level]
        count = max(1, round(len(bucket) * rate)) if bucket else 0
        count = min(count, len(bucket))
        sampled_bucket = rng.sample(bucket, count) if count > 0 else []
        sampled.extend(sampled_bucket)
        result.breakdown[risk_level.value] = len(sampled_bucket)

    result.traces = sampled
    logger.info(
        "Sampler: sampled",
        special=result.breakdown.get("special", 0),
        high=result.breakdown.get("high", 0),
        medium=result.breakdown.get("medium", 0),
        low=result.breakdown.get("low", 0),
        total=len(sampled),
    )
    return result
