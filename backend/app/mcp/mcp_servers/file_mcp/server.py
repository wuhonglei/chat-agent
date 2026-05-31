"""
File MCP Service
提供文件操作与搜索服务
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from app.mcp.mcp_servers.file_mcp.base import ToolContext
from app.mcp.mcp_servers.file_mcp.edit_file import EditFileTool
from app.mcp.mcp_servers.file_mcp.read_file import ReadFileTool
from app.mcp.mcp_servers.file_mcp.search_files import SearchFilesTool
from app.mcp.mcp_servers.file_mcp.write_file import WriteFileTool

mcp = FastMCP(name="File MCP Service")

# Tool instances
_read_file = ReadFileTool()
_write_file = WriteFileTool()
_edit_file = EditFileTool()
_search_files = SearchFilesTool()


@mcp.tool(name="read_file")
async def read_file(
    file_path: str = Field(
        description="The virtual path to the file to read (e.g. /mnt/user-data/workspace/src/main.py, /mnt/user-data/uploads/report.pdf)"
    ),
    offset: Annotated[
        int,
        Field(
            ge=1,
            description="Line number to start reading from (1-based index)",
        ),
    ] = 1,
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=1000,
            description="Number of lines to read (useful for long files)",
        ),
    ] = 1000,
) -> ToolResult:
    """Reads a file from the workspace filesystem."""
    ctx = ToolContext()
    result = await _read_file.execute(
        {"file_path": file_path, "offset": offset, "limit": limit},
        ctx,
    )
    return ToolResult(
        content=result.content, structured_content=result.structured_content
    )


@mcp.tool(name="write_file")
async def write_file(
    file_path: str = Field(
        description="The virtual path to the file to write (under /mnt/user-data/workspace/ or /mnt/user-data/outputs/)"
    ),
    content: str = Field(
        description="The content to write to the file, maxlength is 100000"
    ),
    append: bool = Field(
        default=False,
        description="Whether to append to the file instead of overwriting it",
    ),
) -> ToolResult:
    """Writes a file to the workspace filesystem."""
    ctx = ToolContext()
    result = await _write_file.execute(
        {"file_path": file_path, "content": content, "append": append},
        ctx,
    )
    return ToolResult(
        content=result.content, structured_content=result.structured_content
    )


@mcp.tool(name="edit_file")
async def edit_file(
    file_path: str = Field(description="The virtual path to the file to modify"),
    old_string: str = Field(description="The text to replace"),
    new_string: str = Field(
        description="The text to replace it with (must be different from old_string)"
    ),
    replace_all: bool = Field(
        default=False,
        description="Replace all occurrences of old_string (default: false)",
    ),
) -> ToolResult:
    """Performs exact string replacements in files."""
    ctx = ToolContext()
    result = await _edit_file.execute(
        {
            "file_path": file_path,
            "old_string": old_string,
            "new_string": new_string,
            "replace_all": replace_all,
        },
        ctx,
    )
    return ToolResult(
        content=result.content, structured_content=result.structured_content
    )


@mcp.tool(name="search_files")
async def search_files(
    pattern: str = Field(
        description="Regex pattern for content search, or glob pattern (e.g., '*.py') for file search"
    ),
    target: Literal["content", "files"] = Field(
        default="content",
        description="'content' searches inside file contents, 'files' searches for files by name",
    ),
    path: str = Field(
        default=".",
        description="Directory or file to search in (default: current working directory)",
    ),
    file_glob: str | None = Field(
        default=None,
        description="Filter files by pattern in grep mode (e.g., '*.py' to only search Python files)",
    ),
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=500,
            description="Maximum number of results to return (default: 50)",
        ),
    ] = 50,
    offset: Annotated[
        int,
        Field(
            ge=0,
            description="Skip first N results for pagination (default: 0)",
        ),
    ] = 0,
    output_mode: Literal["content", "files_only", "count"] = Field(
        default="content",
        description="Output format for grep mode: 'content' shows matching lines with line numbers, 'files_only' lists file paths, 'count' shows match counts per file",
    ),
    context: Annotated[
        int,
        Field(
            ge=0,
            le=10,
            description="Number of context lines before and after each match (grep mode only)",
        ),
    ] = 0,
) -> ToolResult:
    """Search file contents or find files by name. Use this instead of grep/rg/find/ls in terminal. Ripgrep-backed, faster than shell equivalents."""
    ctx = ToolContext()
    result = await _search_files.execute(
        {
            "pattern": pattern,
            "target": target,
            "path": path,
            "file_glob": file_glob,
            "limit": limit,
            "offset": offset,
            "output_mode": output_mode,
            "context": context,
        },
        ctx,
    )
    return ToolResult(
        content=result.content, structured_content=result.structured_content
    )
