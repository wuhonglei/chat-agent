"""write_file tool implementation."""

from __future__ import annotations

from typing import Any

from app.mcp.mcp_servers.file_mcp.base import ToolBase, ToolContext, ToolResult
from app.mcp.mcp_servers.file_mcp.utils import ensure_write_quota, resolve_virtual_path
from app.utils.logger import logger
from app.vfs.config import vfs_config
from app.vfs.paths import get_paths
from app.vfs.resolver import PathPermission


class WriteFileTool(ToolBase):
    """Writes a file to the workspace filesystem."""

    name = "write_file"
    description = "Writes a file to the workspace filesystem."

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute write_file tool."""
        file_path = arguments.get("file_path", "")
        content = arguments.get("content", "")
        append = arguments.get("append", False)

        if not file_path:
            return ToolResult(content="Error: file_path is required", is_error=True)

        # Validate content size
        if len(content) > vfs_config.write_max_chars:
            return ToolResult(
                content=f"Error: Content exceeds maximum size of {vfs_config.write_max_chars} characters",
                is_error=True,
            )

        try:
            writable_prefixes = (
                vfs_config.workspace_prefix,
                vfs_config.outputs_prefix,
            )
            if not file_path.startswith(writable_prefixes):
                return ToolResult(
                    content=(
                        "Error: Write operation only allowed under "
                        f"{vfs_config.workspace_prefix} or {vfs_config.outputs_prefix}"
                    ),
                    is_error=True,
                )

            physical_path = resolve_virtual_path(
                file_path, ctx.user_id, ctx.conversation_id, PathPermission.READ_WRITE
            )

            workspace_root = get_paths().ensure_sandbox_work_dir(
                ctx.user_id, ctx.conversation_id
            )

            # Check write quota
            ensure_write_quota(workspace_root, target=physical_path, content=content)

            # Create parent directories
            physical_path.parent.mkdir(parents=True, exist_ok=True)

            # Write or append content
            if append and physical_path.exists():
                existing = physical_path.read_text(encoding="utf-8", errors="replace")
                content = existing + content

            physical_path.write_text(content, encoding="utf-8")

            logger.info(
                "File written",
                file_path=file_path,
                append=append,
                bytes=len(content.encode("utf-8")),
            )

            return ToolResult(
                content=f"File written: {file_path}",
                structured_content={
                    "path": file_path,
                    "append": append,
                    "size": len(content.encode("utf-8")),
                },
            )

        except Exception as e:
            logger.error("write_file failed", error=e, file_path=file_path)
            return ToolResult(content=f"Error: {e}", is_error=True)
