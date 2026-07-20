"""
Skill Manager MCP Service
提供 Agent Skill 加载服务
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from app.mcp.mcp_servers.file_mcp.base import ToolContext, to_fastmcp_tool_result
from app.mcp.mcp_servers.skill_manager_mcp.load_skill import LoadSkillTool

mcp = FastMCP(name="Skill Manager MCP Service")

_load_skill = LoadSkillTool()


@mcp.tool(name="load_skill")
async def load_skill(
    name: str = Field(description="The skill name (unique identifier) to load"),
) -> ToolResult:
    """Load a skill document by name. Returns the skill's markdown content."""
    ctx = ToolContext()
    result = await _load_skill.execute({"name": name}, ctx)
    return to_fastmcp_tool_result(result)
