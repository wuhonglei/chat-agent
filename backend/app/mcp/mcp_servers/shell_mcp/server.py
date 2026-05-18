"""
Shell MCP Service
提供沙箱化的命令执行服务
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from app.mcp.mcp_servers.file_mcp.base import ToolContext
from app.mcp.mcp_servers.shell_mcp.shell import ShellTool

mcp = FastMCP(name="Shell MCP Service")

# Tool instance
_shell_tool = ShellTool()


@mcp.tool(name="shell")
async def shell(
    command: str = Field(
        description="The shell command to execute."
    ),
    description: str = Field(
        description="Clear, concise summary (5-10 words) of what this command does."
    ),
    timeout: Annotated[
        int,
        Field(
            ge=1,
            le=600000,
            description="Optional timeout for command execution (in milliseconds, max: 600000)",
        ),
    ] = 30000,
) -> ToolResult:
    """Execute shell commands in a sandboxed environment with proper security measures."""
    ctx = ToolContext()

    result = await _shell_tool.execute(
        {
            "command": command,
            "description": description,
            "timeout": timeout,
        },
        user_id=ctx.user_id,
        workspace_id=ctx.workspace_id,
    )
    return ToolResult(content=result)


async def initialize_shell_executor(workspace_path: Path) -> None:
    """Initialize the shell executor with workspace path."""
    await _shell_tool.initialize(workspace_path)


async def cleanup_shell_executor() -> None:
    """Cleanup shell executor resources."""
    await _shell_tool.cleanup()
