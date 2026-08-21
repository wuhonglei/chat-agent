"""load_skill tool implementation."""

from __future__ import annotations

from typing import Any

from app.agent_skills.render import render_skill_content, resource_base_from_location
from app.mcp.mcp_servers.file_mcp.base import ToolBase, ToolContext, ToolResult
from app.utils.logger import logger


class LoadSkillTool(ToolBase):
    """Load a skill document by name."""

    name = "load_skill"
    description = (
        "Load the full instructions for an available skill. Call this with the exact "
        "skill name from the session skill catalog before acting on a task that names "
        "or clearly matches that skill."
    )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute load_skill tool."""
        skill_name = arguments.get("name", "")

        if not skill_name:
            return ToolResult(content="Error: name is required", is_error=True)

        try:
            from app.agent_skills import get_skill_registry

            document = get_skill_registry(ctx.user_id or None).load(skill_name)
            resource_base = resource_base_from_location(document.manifest.location)
            content = render_skill_content(
                name=document.manifest.name,
                content=document.body,
                resource_base=resource_base,
            )

            logger.info(
                "Skill loaded",
                skill_name=skill_name,
                body_length=len(document.body),
            )

            return ToolResult(
                content=content,
            )

        except Exception as e:
            logger.error("load_skill failed", error=e, skill_name=skill_name)
            message = str(e)
            if not message.startswith("Error:"):
                message = f"Error: {message}"
            return ToolResult(content=message, is_error=True)
