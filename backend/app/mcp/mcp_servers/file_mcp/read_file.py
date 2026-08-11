"""read_file tool implementation."""

from __future__ import annotations

from typing import Any

from app.mcp.mcp_servers.file_mcp.base import ToolBase, ToolContext, ToolResult
from app.mcp.mcp_servers.file_mcp.utils import (
    non_text_file_reason,
    resolve_virtual_path,
    truncate_content,
)
from app.utils.logger import logger
from app.vfs.resolver import PathPermission

READ_FILE_DESCRIPTION = (
    "Reads a text file from the workspace filesystem (line-based offset/limit). "
    "Do NOT use for images (png/jpg/jpeg/gif/webp/…) or other binary files "
    "(pdf/xlsx/docx/pptx/zip/…). Those cannot be read as text; for PDF/Office "
    "uploads prefer the derived Markdown under uploads/derived/. For images "
    "already attached in the user message, interpret them directly (vision) "
    "instead of calling this tool."
)


class ReadFileTool(ToolBase):
    """Reads a text file from the workspace filesystem."""

    name = "read_file"
    description = READ_FILE_DESCRIPTION

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute read_file tool."""
        file_path = arguments.get("file_path", "")
        offset = arguments.get("offset", 1)
        limit = arguments.get("limit", 2000)

        if not file_path:
            return ToolResult(content="Error: file_path is required", is_error=True)

        try:
            # Resolve virtual path to physical
            physical_path = resolve_virtual_path(
                file_path, ctx.user_id, ctx.conversation_id, PathPermission.READ_ONLY
            )

            if not physical_path.is_file():
                return ToolResult(
                    content=f"Error: {file_path} is not a file",
                    is_error=True,
                )

            size = physical_path.stat().st_size
            kind = non_text_file_reason(physical_path)
            if kind is not None:
                if kind == "image":
                    message = (
                        f"Error: {file_path} is an image ({size} bytes) and cannot be "
                        "read as text via read_file. If the image is already in the "
                        "user message, interpret it directly; do not call read_file "
                        "on image paths."
                    )
                else:
                    message = (
                        f"Error: {file_path} is a binary file ({size} bytes) and "
                        "cannot be read as text via read_file. For PDF/Excel/Word/"
                        "PowerPoint uploads, read the derived Markdown under "
                        "uploads/derived/ instead."
                    )
                return ToolResult(
                    content=message,
                    is_error=True,
                    structured_content={
                        "path": file_path,
                        "size": size,
                        "kind": kind,
                        "rejected": True,
                    },
                )

            # Read file content
            content = physical_path.read_text(encoding="utf-8", errors="replace")

            # Apply line-based pagination
            lines = content.splitlines(keepends=True)
            total_lines = len(lines)

            # Convert to 0-based indexing
            start_idx = max(0, offset - 1)
            end_idx = min(total_lines, start_idx + limit)

            selected_lines = lines[start_idx:end_idx]
            result_content = "".join(selected_lines)

            # Truncate if too long
            result_content, truncated = truncate_content(result_content)

            if truncated:
                result_content += "\n\n[Truncated by system limit]"

            logger.info(
                "File read",
                file_path=file_path,
                offset=offset,
                limit=limit,
                total_lines=total_lines,
                truncated=truncated,
            )

            return ToolResult(
                content=result_content,
                structured_content={
                    "path": file_path,
                    "offset": offset,
                    "limit": limit,
                    "total_lines": total_lines,
                    "truncated": truncated,
                    "size": size,
                },
            )

        except Exception as e:
            logger.error("read_file failed", error=e, file_path=file_path)
            return ToolResult(content=f"Error: {e}", is_error=True)
