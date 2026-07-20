"""
Shell MCP Service
提供沙箱化的命令执行服务
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import BeforeValidator, Field

from app.mcp.mcp_servers.file_mcp.base import ToolContext
from app.mcp.mcp_servers.shell_mcp.shell import ShellTool

mcp = FastMCP(name="Shell MCP Service")

# Tool instance (per-worker singleton; executors cached per workspace inside)
_shell_tool = ShellTool()


def _coerce_timeout(value: object) -> object:
    """Accept numeric strings from LLM tool calls (e.g. '30000')."""
    if isinstance(value, bool):
        raise TypeError("timeout must be an integer")
    if isinstance(value, str):
        return int(value.strip())
    return value


@mcp.tool(name="exec")
async def shell(
    command: str = Field(description="The shell command to execute."),
    timeout: Annotated[
        int,
        BeforeValidator(_coerce_timeout),
        Field(
            ge=1,
            le=60000,
            description="Optional timeout for command execution (in milliseconds, max: 60000)",
        ),
    ] = 30000,
) -> ToolResult:
    """Execute shell commands in a sandboxed environment with proper security measures."""
    ctx = ToolContext()

    result = await _shell_tool.execute(
        {
            "command": command,
            "timeout": timeout,
        },
        user_id=ctx.user_id,
        conversation_id=ctx.conversation_id,
    )
    structured = (
        result.structured_content.model_dump(mode="json")
        if result.structured_content is not None
        else None
    )
    return ToolResult(content=result.content, structured_content=structured)


async def initialize_shell_executor(workspace_path: Path) -> None:
    """Pre-initialize shell sandbox for an explicit path (tests/scripts only).

    Production traffic should rely on lazy init via ShellTool.get_or_create_executor
    when the shell tool is invoked with user_id and conversation_id from request context.
    """
    await _shell_tool.initialize(workspace_path)


async def cleanup_shell_executor() -> None:
    """Cleanup all cached shell executors (tests/teardown)."""
    await _shell_tool.cleanup()
