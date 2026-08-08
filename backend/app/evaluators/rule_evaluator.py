"""实时规则评估器：每轮问答结束后同步执行，写 Langfuse score。"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.observability import score_observation
from app.mcp.tool_naming import ToolRoute
from app.schemas.chat import (
    AssistantResponse,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    count_tool_use_blocks,
)
from app.utils.logger import logger


def build_tool_whitelist(
    agent_mode: int,
    tools_map: dict[str, ToolRoute],
) -> set[str]:
    """从 MCP tools_map 构建当前 agent_mode 的工具白名单。"""
    if agent_mode > 0:
        server_names = set(settings.mcp.agent_mode_servers)
    else:
        server_names = set(settings.mcp.normal_mode_servers)
    return {
        name for name, route in tools_map.items() if route.server_name in server_names
    }


def evaluate_and_score(
    *,
    span: Any,
    assistant_response: AssistantResponse,
    agent_mode: int,
    tool_whitelist: set[str],
) -> dict[str, Any]:
    """入口函数：计算 P0 指标，写 Langfuse score，返回规则分数 dict。

    返回值示例::

        {
            "valid_answer": True,
            "tool_whitelist_ok": True,
            "tool_call_count": 2,
            "tool_loop_detected": False,
            "guardrail_error_count": 0,
        }

    ``agent_mode`` 由调用方用于构建 ``tool_whitelist``；评估逻辑本身只依赖白名单集合。
    失败只告警不冒泡，返回空 dict。
    """
    _ = agent_mode
    try:
        return _do_evaluate(
            span=span,
            assistant_response=assistant_response,
            tool_whitelist=tool_whitelist,
        )
    except Exception as exc:
        logger.warning(
            "Rule evaluator failed",
            error=exc,
            error_type=type(exc).__name__,
        )
        return {}


def _do_evaluate(
    *,
    span: Any,
    assistant_response: AssistantResponse,
    tool_whitelist: set[str],
) -> dict[str, Any]:
    content = assistant_response.content
    content_blocks = assistant_response.content_blocks
    scores: dict[str, Any] = {}

    # --- valid_answer ---
    # 检查最后一个 block 是否为非空 TextBlock（模型最终回复）
    # 而非拼接所有 TextBlock（中间轮文本输出会误判）
    last_block = content_blocks[-1] if content_blocks else None
    is_valid = isinstance(last_block, TextBlock) and len(last_block.text.strip()) > 0
    score_observation(span, name="valid_answer", value=is_valid)
    scores["valid_answer"] = is_valid

    # --- tool_whitelist_ok ---
    has_unnamed_tool = any(
        isinstance(block, ToolUseBlock) and not block.name for block in content_blocks
    )
    called_tools = {
        block.name
        for block in content_blocks
        if isinstance(block, ToolUseBlock) and block.name
    }
    _write_called_tools_metadata(span, called_tools)
    whitelist_ok = (not has_unnamed_tool) and called_tools.issubset(tool_whitelist)
    score_observation(
        span,
        name="tool_whitelist_ok",
        value=whitelist_ok,
        comment=f"called={called_tools}" if not whitelist_ok else None,
    )
    scores["tool_whitelist_ok"] = whitelist_ok
    scores["called_tools"] = sorted(called_tools)

    # --- tool_call_count ---
    tool_count = count_tool_use_blocks(content_blocks)
    score_observation(
        span, name="tool_call_count", value=tool_count, data_type="NUMERIC"
    )
    scores["tool_call_count"] = tool_count

    # --- tool_loop_detected ---
    guardrail_error_count = sum(
        1
        for block in content_blocks
        if isinstance(block, ToolResultBlock)
        and block.is_error
        and block.error_source in ("guardrail_block", "guardrail_halt")
    )
    loop_detected = guardrail_error_count > 0
    score_observation(span, name="tool_loop_detected", value=loop_detected)
    scores["tool_loop_detected"] = loop_detected
    scores["guardrail_error_count"] = guardrail_error_count

    return scores


def _write_called_tools_metadata(span: Any, called_tools: set[str]) -> None:
    """将 called_tools 写入 Langfuse span metadata，供批量评估风险分层使用。"""
    if span is None:
        return
    try:
        span.update(metadata={"called_tools": sorted(called_tools)})
    except Exception as exc:
        logger.warning(
            "Failed to write called_tools metadata",
            error=exc,
            error_type=type(exc).__name__,
        )
