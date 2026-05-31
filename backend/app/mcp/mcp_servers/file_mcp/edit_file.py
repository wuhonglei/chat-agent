"""edit_file tool implementation."""

from __future__ import annotations

from typing import Any

from app.mcp.mcp_servers.file_mcp.base import ToolBase, ToolContext, ToolResult
from app.mcp.mcp_servers.file_mcp.utils import ensure_write_quota, resolve_virtual_path
from app.utils.logger import logger
from app.vfs.config import vfs_config
from app.vfs.paths import get_paths
from app.vfs.resolver import PathPermission


class EditFileTool(ToolBase):
    """Performs exact string replacements in files."""

    name = "edit_file"
    description = "Performs exact string replacements in files."

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute edit_file tool."""
        file_path = arguments.get("file_path", "")
        old_string = arguments.get("old_string", "")
        new_string = arguments.get("new_string", "")
        replace_all = arguments.get("replace_all", False)

        if not file_path:
            return ToolResult(content="Error: file_path is required", is_error=True)

        if not old_string:
            return ToolResult(
                content="Error: old_string must not be empty", is_error=True
            )

        if old_string == new_string:
            return ToolResult(
                content="Error: old_string and new_string must be different",
                is_error=True,
            )

        try:
            writable_prefixes = (
                vfs_config.workspace_prefix,
                vfs_config.outputs_prefix,
                vfs_config.skills_custom_prefix,
            )
            if not file_path.startswith(writable_prefixes):
                return ToolResult(
                    content=(
                        "Error: Edit operation only allowed under "
                        f"{vfs_config.workspace_prefix}, {vfs_config.outputs_prefix}, "
                        f"or {vfs_config.skills_custom_prefix}"
                    ),
                    is_error=True,
                )

            is_custom_skill = file_path.startswith(vfs_config.skills_custom_prefix)

            physical_path = resolve_virtual_path(
                file_path, ctx.user_id, ctx.conversation_id, PathPermission.READ_WRITE
            )

            if not physical_path.is_file():
                return ToolResult(
                    content=f"Error: {file_path} does not exist or is not a file",
                    is_error=True,
                )

            # Read current content
            content = physical_path.read_text(encoding="utf-8", errors="replace")

            # Check if old_string exists
            match_count = content.count(old_string)
            if match_count == 0:
                return ToolResult(
                    content="Error: old_string not found in file",
                    is_error=True,
                )

            # Check uniqueness (unless replace_all)
            if not replace_all and match_count > 1:
                return ToolResult(
                    content="Error: old_string matched multiple locations. Set replace_all=true or provide a unique snippet.",
                    is_error=True,
                )

            # Perform replacement
            if replace_all:
                updated_content = content.replace(old_string, new_string)
                applied_count = match_count
            else:
                updated_content = content.replace(old_string, new_string, 1)
                applied_count = 1

            if not is_custom_skill:
                workspace_root = get_paths().ensure_sandbox_work_dir(
                    ctx.user_id, ctx.conversation_id
                )
                ensure_write_quota(
                    workspace_root, target=physical_path, content=updated_content
                )

            # Write updated content
            physical_path.write_text(updated_content, encoding="utf-8")

            logger.info(
                "File edited",
                file_path=file_path,
                applied_count=applied_count,
                replace_all=replace_all,
            )

            return ToolResult(
                content=f"Edited file: {file_path} (applied={applied_count})",
                structured_content={
                    "path": file_path,
                    "applied_count": applied_count,
                    "replace_all": replace_all,
                },
            )

        except Exception as e:
            logger.error("edit_file failed", error=e, file_path=file_path)
            return ToolResult(content=f"Error: {e}", is_error=True)
