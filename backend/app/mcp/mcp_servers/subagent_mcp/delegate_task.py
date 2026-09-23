"""delegate_task tool: hand one self-contained task to a zero-context subagent."""

from __future__ import annotations

from app.mcp import get_mcp_client_manager
from app.mcp.mcp_servers.file_mcp.base import ToolResult
from app.services.subagent.service import SubagentService

DELEGATE_TASK_DESCRIPTION = (
    "把一个自包含的子任务委派给对当前对话一无所知的子 agent：它看不到本对话和你的工具结果，"
    "但能用文件、检索、执行类工具独立完成任务。"
    "适合互相独立的工作，或搜索、阅读大量文件会淹没主上下文的情况；"
    "委派后直接采信报告，不要自己重复执行同一任务。"
    "不要用于单文件修改、一步就能完成的操作、需要用户中途确认的任务，"
    "也不要要求子 agent 再委派——它的工具面不含委派工具。"
    "goal 必须独立成立、不含 TODO 占位标记。"
    "只返回子 agent 的最终报告，不返回它的工具调用；执行耗时可能较长。"
    "多个互不依赖的任务，可在同一轮并行发起多次调用。"
)


async def execute_delegate_task(*, goal: str, context: str | None) -> ToolResult:
    service = SubagentService(get_mcp_client_manager())
    return await service.run(goal=goal, context=context)
