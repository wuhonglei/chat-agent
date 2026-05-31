"""present_files tool implementation."""

from __future__ import annotations

from typing import Any

from app.mcp.mcp_servers.file_mcp.base import ToolBase, ToolContext, ToolResult
from app.mcp.mcp_servers.file_mcp.utils import resolve_virtual_path
from app.utils.logger import logger
from app.vfs.config import vfs_config
from app.vfs.resolver import PathPermission


def _normalize_presented_filepath(
    user_id: str,
    conversation_id: str,
    filepath: str,
) -> str:
    """Normalize a virtual outputs path for presentation."""
    outputs_prefix = vfs_config.outputs_prefix
    filepath = filepath.strip()
    if not filepath.startswith(outputs_prefix):
        raise ValueError(
            f"Only virtual paths under {outputs_prefix} are allowed: {filepath}"
        )

    actual_path = resolve_virtual_path(
        filepath,
        user_id,
        conversation_id,
        PathPermission.READ_ONLY,
        must_exist=False,
    )
    if not actual_path.is_file():
        raise ValueError(f"File does not exist: {filepath}")

    relative = filepath[len(outputs_prefix) :].lstrip("/")
    return f"{outputs_prefix.rstrip('/')}/{relative}"


class PresentFilesTool(ToolBase):
    """Presents output files to the user as deliverable artifacts."""

    name = "present_files"
    description = "Make files visible to the user for viewing and download in the client interface."

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute present_files tool."""
        filepaths = arguments.get("filepaths")
        if not filepaths or not isinstance(filepaths, list):
            return ToolResult(
                content="Error: filepaths is required and must be a non-empty list",
                is_error=True,
            )

        normalized: list[str] = []
        try:
            for filepath in filepaths:
                if not isinstance(filepath, str) or not filepath.strip():
                    raise ValueError("Each filepath must be a non-empty string")
                normalized.append(
                    _normalize_presented_filepath(
                        ctx.user_id,
                        ctx.conversation_id,
                        filepath,
                    )
                )
        except ValueError as exc:
            logger.warning("present_files failed", error=exc, filepaths=filepaths)
            return ToolResult(content=f"Error: {exc}", is_error=True)

        logger.info("Files presented", presented_paths=normalized)
        paths_str = ", ".join(normalized)
        return ToolResult(
            content=f"Successfully presented files: {paths_str}",
            structured_content={"presented_paths": normalized},
        )
