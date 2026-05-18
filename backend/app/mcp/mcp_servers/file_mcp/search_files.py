"""search_files tool implementation."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from app.mcp.mcp_servers.file_mcp.base import ToolBase, ToolContext, ToolResult
from app.mcp.mcp_servers.file_mcp.utils import resolve_virtual_path
from app.utils.logger import logger
from app.vfs.mapper import MappingContext, VirtualPathMapper
from app.vfs.resolver import PathPermission


class SearchFilesTool(ToolBase):
    """Search file contents or find files by name."""

    name = "search_files"
    description = "Search file contents or find files by name. Use this instead of grep/rg/find/ls in terminal. Ripgrep-backed, faster than shell equivalents."

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute search_files tool."""
        pattern = arguments.get("pattern", "")
        target = arguments.get("target", "content")
        path = arguments.get("path", ".")
        file_glob = arguments.get("file_glob")
        limit = arguments.get("limit", 50)
        offset = arguments.get("offset", 0)
        output_mode = arguments.get("output_mode", "content")
        context = arguments.get("context", 0)

        if not pattern:
            return ToolResult(content="Error: pattern is required", is_error=True)

        try:
            # Resolve search directory
            if path == ".":
                # Default to workspace root
                from app.mcp.mcp_servers.file_mcp.utils import get_workspace_root

                search_dir = get_workspace_root(ctx.user_id, ctx.workspace_id)
            else:
                search_dir = resolve_virtual_path(
                    path, ctx.user_id, ctx.workspace_id, PathPermission.READ_ONLY
                )

            if not search_dir.exists():
                return ToolResult(
                    content=f"Error: Path does not exist: {path}", is_error=True
                )

            # Execute search
            if target == "files":
                results = await self._search_files(
                    search_dir, pattern, limit, offset
                )
            else:
                results = await self._search_content(
                    search_dir, pattern, file_glob, limit, offset, output_mode, context
                )

            # Replace physical paths with virtual paths
            mapper = VirtualPathMapper()
            mapping_ctx = MappingContext(
                user_id=ctx.user_id, workspace_id=ctx.workspace_id
            )

            # Convert results to virtual paths
            virtual_results = []
            for line in results:
                virtual_line = mapper._replace_physical_paths(line, mapping_ctx)
                virtual_results.append(virtual_line)

            content = "\n".join(virtual_results)

            # Truncate if too long
            max_output = 50000
            truncated = False
            if len(content) > max_output:
                content = content[:max_output]
                truncated = True
                content += "\n\n[Output truncated]"

            logger.info(
                "Search completed",
                pattern=pattern,
                target=target,
                results_count=len(virtual_results),
                truncated=truncated,
            )

            return ToolResult(
                content=content,
                structured_content={
                    "pattern": pattern,
                    "target": target,
                    "results_count": len(virtual_results),
                    "truncated": truncated,
                },
            )

        except Exception as e:
            logger.error("search_files failed", error=e, pattern=pattern)
            return ToolResult(content=f"Error: {e}", is_error=True)

    async def _search_files(
        self, search_dir: Path, pattern: str, limit: int, offset: int
    ) -> list[str]:
        """Search files by glob pattern."""
        try:
            # Use rg --files if available
            cmd = ["rg", "--files", "--glob", pattern, str(search_dir)]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                files = stdout.decode("utf-8", errors="replace").strip().split("\n")
                files = [f for f in files if f]
                # Sort by modification time
                files.sort(
                    key=lambda f: Path(f).stat().st_mtime if Path(f).exists() else 0,
                    reverse=True,
                )
                return files[offset : offset + limit]
            else:
                # Fallback to Python glob
                return self._python_glob_search(search_dir, pattern, limit, offset)

        except FileNotFoundError:
            # rg not installed, fallback to Python glob
            return self._python_glob_search(search_dir, pattern, limit, offset)

    def _python_glob_search(
        self, search_dir: Path, pattern: str, limit: int, offset: int
    ) -> list[str]:
        """Fallback glob search using Python."""
        files = sorted(
            search_dir.rglob(pattern),
            key=lambda f: f.stat().st_mtime if f.exists() else 0,
            reverse=True,
        )
        return [str(f) for f in files[offset : offset + limit]]

    async def _search_content(
        self,
        search_dir: Path,
        pattern: str,
        file_glob: str | None,
        limit: int,
        offset: int,
        output_mode: str,
        context: int,
    ) -> list[str]:
        """Search file contents using ripgrep."""
        try:
            cmd = ["rg", "--no-heading", "--color=never"]

            if output_mode == "content":
                cmd.append("--line-number")
            elif output_mode == "files_only":
                cmd.append("--files-with-matches")
            elif output_mode == "count":
                cmd.append("--count")

            if file_glob:
                cmd.extend(["--glob", file_glob])

            if context > 0:
                cmd.extend(["--context", str(context)])

            # Add pattern and path
            cmd.extend([pattern, str(search_dir)])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                lines = stdout.decode("utf-8", errors="replace").strip().split("\n")
                lines = [line for line in lines if line]
                return lines[offset : offset + limit]
            elif proc.returncode == 1:
                # No matches
                return []
            else:
                # Error, fallback to Python
                return self._python_content_search(
                    search_dir, pattern, file_glob, limit, offset, output_mode
                )

        except FileNotFoundError:
            return self._python_content_search(
                search_dir, pattern, file_glob, limit, offset, output_mode
            )

    def _python_content_search(
        self,
        search_dir: Path,
        pattern: str,
        file_glob: str | None,
        limit: int,
        offset: int,
        output_mode: str,
    ) -> list[str]:
        """Fallback content search using Python regex."""
        try:
            regex = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        results = []
        files = search_dir.rglob(file_glob or "*")

        for file_path in files:
            if not file_path.is_file():
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()

                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        if output_mode == "content":
                            results.append(f"{file_path}:{i}:{line}")
                        elif output_mode == "files_only":
                            results.append(str(file_path))
                            break
                        elif output_mode == "count":
                            count = len(regex.findall(content))
                            results.append(f"{file_path}:{count}")
                            break
            except (OSError, UnicodeDecodeError):
                continue

            if len(results) >= offset + limit:
                break

        return results[offset : offset + limit]
