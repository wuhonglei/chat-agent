"""Tests for file MCP server."""

from __future__ import annotations

import pytest

from app.mcp.mcp_servers.file_mcp.base import ToolContext
from app.mcp.mcp_servers.file_mcp.edit_file import EditFileTool
from app.mcp.mcp_servers.file_mcp.read_file import ReadFileTool
from app.mcp.mcp_servers.file_mcp.write_file import WriteFileTool
from app.utils.logger import conversation_id_var, user_id_var


@pytest.fixture
def ctx() -> ToolContext:
    # Set contextvars for testing
    user_id_var.set("test_user")
    conversation_id_var.set("test_workspace")
    return ToolContext()


@pytest.mark.asyncio
async def test_read_file_not_found(ctx: ToolContext) -> None:
    tool = ReadFileTool()
    result = await tool.execute({"file_path": "/workspace/nonexistent.txt"}, ctx)
    assert result.is_error


@pytest.mark.asyncio
async def test_write_file_invalid_path(ctx: ToolContext) -> None:
    tool = WriteFileTool()
    result = await tool.execute(
        {"file_path": "/uploads/test.txt", "content": "hello"},
        ctx,
    )
    assert result.is_error
    assert "only allowed under" in result.content


@pytest.mark.asyncio
async def test_edit_file_empty_old_string(ctx: ToolContext) -> None:
    tool = EditFileTool()
    result = await tool.execute(
        {
            "file_path": "/workspace/test.txt",
            "old_string": "",
            "new_string": "new",
        },
        ctx,
    )
    assert result.is_error
    assert "must not be empty" in result.content


@pytest.mark.asyncio
async def test_edit_file_same_strings(ctx: ToolContext) -> None:
    tool = EditFileTool()
    result = await tool.execute(
        {
            "file_path": "/workspace/test.txt",
            "old_string": "same",
            "new_string": "same",
        },
        ctx,
    )
    assert result.is_error
    assert "must be different" in result.content
