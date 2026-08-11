"""Tests for file MCP server."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.mcp.mcp_servers.file_mcp.base import ToolContext
from app.mcp.mcp_servers.file_mcp.edit_file import EditFileTool
from app.mcp.mcp_servers.file_mcp.read_file import READ_FILE_DESCRIPTION, ReadFileTool
from app.mcp.mcp_servers.file_mcp.utils import non_text_file_reason
from app.mcp.mcp_servers.file_mcp.write_file import WriteFileTool
from app.utils.context import set_request_context
from app.vfs.config import vfs_config
from app.vfs.paths import get_paths


@pytest.fixture
def ctx() -> ToolContext:
    # Set contextvars for testing
    set_request_context(user_id="test_user", conversation_id="test_workspace")
    return ToolContext()


@pytest.fixture
def uploads_dir(ctx: ToolContext) -> Path:
    paths = get_paths()
    directory = paths.sandbox_uploads_dir("test_user", "test_workspace")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@pytest.mark.asyncio
async def test_read_file_not_found(ctx: ToolContext) -> None:
    tool = ReadFileTool()
    result = await tool.execute(
        {"file_path": f"{vfs_config.workspace_prefix}nonexistent.txt"}, ctx
    )
    assert result.is_error


@pytest.mark.asyncio
async def test_read_file_rejects_image_by_extension(
    ctx: ToolContext, uploads_dir: Path
) -> None:
    image_path = uploads_dir / "shot.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    tool = ReadFileTool()
    result = await tool.execute(
        {"file_path": f"{vfs_config.uploads_prefix}shot.png"},
        ctx,
    )
    assert result.is_error
    assert "image" in result.content.lower()
    assert "cannot be read as text" in result.content
    assert result.structured_content is not None
    assert result.structured_content["kind"] == "image"
    assert result.structured_content["rejected"] is True


@pytest.mark.asyncio
async def test_read_file_rejects_pdf_by_extension(
    ctx: ToolContext, uploads_dir: Path
) -> None:
    pdf_path = uploads_dir / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake binary content")

    tool = ReadFileTool()
    result = await tool.execute(
        {"file_path": f"{vfs_config.uploads_prefix}doc.pdf"},
        ctx,
    )
    assert result.is_error
    assert "binary" in result.content.lower()
    assert "derived" in result.content.lower()
    assert result.structured_content is not None
    assert result.structured_content["kind"] == "binary"


@pytest.mark.asyncio
async def test_read_file_rejects_image_by_magic_without_ext(
    ctx: ToolContext, uploads_dir: Path
) -> None:
    raw_path = uploads_dir / "noext"
    raw_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"IHDR" + b"\x00" * 8)

    tool = ReadFileTool()
    result = await tool.execute(
        {"file_path": f"{vfs_config.uploads_prefix}noext"},
        ctx,
    )
    assert result.is_error
    assert "image" in result.content.lower()


def test_non_text_file_reason_text_is_none(tmp_path: Path) -> None:
    text_file = tmp_path / "notes.txt"
    text_file.write_text("hello\n", encoding="utf-8")
    assert non_text_file_reason(text_file) is None


def test_read_file_description_mentions_binary_ban() -> None:
    assert "Do NOT use for images" in READ_FILE_DESCRIPTION
    assert "binary" in READ_FILE_DESCRIPTION.lower()


@pytest.mark.asyncio
async def test_write_file_invalid_path(ctx: ToolContext) -> None:
    tool = WriteFileTool()
    result = await tool.execute(
        {"file_path": f"{vfs_config.uploads_prefix}test.txt", "content": "hello"},
        ctx,
    )
    assert result.is_error
    assert "only allowed under" in result.content


@pytest.mark.asyncio
async def test_edit_file_empty_old_string(ctx: ToolContext) -> None:
    tool = EditFileTool()
    result = await tool.execute(
        {
            "file_path": f"{vfs_config.workspace_prefix}test.txt",
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
            "file_path": f"{vfs_config.workspace_prefix}test.txt",
            "old_string": "same",
            "new_string": "same",
        },
        ctx,
    )
    assert result.is_error
    assert "must be different" in result.content
