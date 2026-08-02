"""实时规则评估器：每轮问答结束后同步执行，写 Langfuse score。"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.observability import score_observation
from app.mcp.tool_naming import ToolRoute
from app.schemas.chat import AssistantResponse, ToolUseBlock, count_tool_use_blocks
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
) -> None:
    """入口函数：计算 P0 指标，写 Langfuse score。失败只告警不冒泡。

    ``agent_mode`` 由调用方用于构建 ``tool_whitelist``；评估逻辑本身只依赖白名单集合。
    """
    _ = agent_mode
    try:
        _do_evaluate(
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


def _do_evaluate(
    *,
    span: Any,
    assistant_response: AssistantResponse,
    tool_whitelist: set[str],
) -> None:
    content = assistant_response.content
    content_blocks = assistant_response.content_blocks

    # --- valid_answer ---
    is_valid = len(content.strip()) > 0
    score_observation(span, name="valid_answer", value=is_valid)

    # --- tool_whitelist_ok ---
    has_unnamed_tool = any(
        isinstance(block, ToolUseBlock) and not block.name for block in content_blocks
    )
    called_tools = {
        block.name
        for block in content_blocks
        if isinstance(block, ToolUseBlock) and block.name
    }
    whitelist_ok = (not has_unnamed_tool) and called_tools.issubset(tool_whitelist)
    score_observation(
        span,
        name="tool_whitelist_ok",
        value=whitelist_ok,
        comment=f"called={called_tools}" if not whitelist_ok else None,
    )

    # --- tool_call_count ---
    tool_count = count_tool_use_blocks(content_blocks)
    score_observation(
        span, name="tool_call_count", value=tool_count, data_type="NUMERIC"
    )
