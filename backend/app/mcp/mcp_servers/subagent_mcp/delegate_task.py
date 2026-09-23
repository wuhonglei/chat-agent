"""delegate_task tool: hand one self-contained task to a zero-context subagent."""

from __future__ import annotations

from app.mcp import get_mcp_client_manager
from app.mcp.mcp_servers.file_mcp.base import ToolResult
from app.services.subagent.service import SubagentService

DELEGATE_TASK_DESCRIPTION = (
    "把一个自包含的子任务委派给对当前对话一无所知的子 agent。"
    "适合互相独立的工作，或搜索、阅读大量文件会淹没主上下文的情况。"
    "不要用于单文件修改、一步就能完成的操作，或中途需要用户确认的任务。"
    "goal 必须能独立成立。只返回子 agent 的最终报告，不返回它的工具调用。"
)


async def execute_delegate_task(*, goal: str, context: str | None) -> ToolResult:
    service = SubagentService(get_mcp_client_manager())
    return await service.run(goal=goal, context=context)
