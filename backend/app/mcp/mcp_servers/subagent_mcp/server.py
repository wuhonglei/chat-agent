"""
Subagent MCP Service
把独立子任务委派给一次性子 agent
"""

from __future__ import annotations

from fastmcp import Context, FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from app.mcp.mcp_servers.file_mcp.base import to_fastmcp_tool_result
from app.mcp.mcp_servers.subagent_mcp.delegate_task import (
    DELEGATE_TASK_DESCRIPTION,
    execute_delegate_task,
)
from app.services.subagent.context import (
    activate_published_turn,
    clear_server_task_delegation,
    delegation_token_from_meta,
    get_turn_delegation,
    isolate_turn_delegation,
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
    ctx: Context | None = None,
) -> ToolResult:
    """Delegate one self-contained task and return only the final report."""
    request_context = ctx.request_context if ctx is not None else None
    token = delegation_token_from_meta(
        request_context.meta if request_context is not None else None
    )
    try:
        activated = token is not None and activate_published_turn(token)
        if not activated and get_turn_delegation() is None:
            isolate_turn_delegation()
        result = await execute_delegate_task(goal=goal, context=context)
        return to_fastmcp_tool_result(result)
    finally:
        clear_server_task_delegation()
