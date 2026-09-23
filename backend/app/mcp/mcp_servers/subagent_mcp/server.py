"""
Subagent MCP Service
把独立子任务委派给一次性子 agent
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from app.mcp.mcp_servers.file_mcp.base import to_fastmcp_tool_result
from app.mcp.mcp_servers.subagent_mcp.delegate_task import (
    DELEGATE_TASK_DESCRIPTION,
    execute_delegate_task,
)

mcp = FastMCP(name="Subagent MCP Service")


@mcp.tool(name="delegate_task", description=DELEGATE_TASK_DESCRIPTION)
async def delegate_task(
    goal: str = Field(
        description=(
            "The full task. It must be self-contained: the subagent cannot see "
            "this conversation, your tool results, or the user's earlier messages."
        )
    ),
    context: str | None = Field(
        default=None,
        description=(
            "Optional background that belongs only to this subtask: paths, "
            "constraints, or known errors. Do not paste the whole conversation."
        ),
    ),
) -> ToolResult:
    """Delegate one self-contained task and return only the final report."""
    result = await execute_delegate_task(goal=goal, context=context)
    return to_fastmcp_tool_result(result)
