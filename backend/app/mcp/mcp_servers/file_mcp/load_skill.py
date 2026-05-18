"""load_skill tool implementation."""

from __future__ import annotations

from typing import Any

from app.mcp.mcp_servers.file_mcp.base import ToolBase, ToolContext, ToolResult
from app.utils.logger import logger


class LoadSkillTool(ToolBase):
    """Load a skill document by name."""

    name = "load_skill"
    description = "Load a skill document by name. Returns the skill's markdown content."

    MAX_SKILL_BODY_CHARS = 20000

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute load_skill tool."""
        skill_name = arguments.get("name", "")

        if not skill_name:
            return ToolResult(content="Error: name is required", is_error=True)

        try:
            from app.agent_skills import skill_registry

            document = skill_registry.load(skill_name)
            body = document.body

            # Truncate if too long
            truncated = False
            if len(body) > self.MAX_SKILL_BODY_CHARS:
                body = body[: self.MAX_SKILL_BODY_CHARS]
                truncated = True

            content = body + ("\n\n[Truncated by system limit]" if truncated else "")

            logger.info(
                "Skill loaded",
                skill_name=skill_name,
                truncated=truncated,
                body_length=len(content),
            )

            return ToolResult(
                content=content,
                structured_content={
                    "name": document.manifest.name,
                    "description": document.manifest.description,
                    "truncated": truncated,
                },
            )

        except Exception as e:
            logger.error("load_skill failed", error=e, skill_name=skill_name)
            return ToolResult(content=f"Error: {e}", is_error=True)
