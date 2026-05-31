"""Tests for present_files MCP tool."""

from __future__ import annotations

import pytest

from app.mcp.mcp_servers.file_mcp.base import ToolContext
from app.mcp.mcp_servers.file_mcp.present_files import PresentFilesTool
from app.utils.context import set_request_context
from app.vfs.config import vfs_config
from app.vfs.paths import get_paths


@pytest.fixture
def ctx() -> ToolContext:
    set_request_context(user_id="test_user", conversation_id="test_workspace")
    return ToolContext()


@pytest.fixture
def outputs_report_path(ctx: ToolContext) -> str:
    paths = get_paths()
    paths.ensure_conversation_dirs(ctx.user_id, ctx.conversation_id)
    outputs_dir = paths.sandbox_outputs_dir(ctx.user_id, ctx.conversation_id)
    report = outputs_dir / "report.md"
    report.write_text("# Report", encoding="utf-8")
    return f"{vfs_config.outputs_prefix}report.md"


@pytest.mark.asyncio
async def test_present_files_success(ctx: ToolContext, outputs_report_path: str) -> None:
    tool = PresentFilesTool()
    result = await tool.execute({"filepaths": [outputs_report_path]}, ctx)

    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["presented_paths"] == [outputs_report_path]
    assert "Successfully presented files" in result.content


@pytest.mark.asyncio
async def test_present_files_rejects_host_path(ctx: ToolContext) -> None:
    tool = PresentFilesTool()
    result = await tool.execute(
        {"filepaths": ["/Users/alice/data/user_data/outputs/report.md"]},
        ctx,
    )

    assert result.is_error
    assert "Only virtual paths under" in result.content


@pytest.mark.asyncio
async def test_present_files_rejects_workspace_path(ctx: ToolContext) -> None:
    tool = PresentFilesTool()
    write_tool_path = f"{vfs_config.workspace_prefix}draft.md"
    paths = get_paths()
    paths.ensure_sandbox_work_dir(ctx.user_id, ctx.conversation_id)
    (paths.sandbox_work_dir(ctx.user_id, ctx.conversation_id) / "draft.md").write_text(
        "draft", encoding="utf-8"
    )

    result = await tool.execute({"filepaths": [write_tool_path]}, ctx)

    assert result.is_error
    assert "Only virtual paths under" in result.content


@pytest.mark.asyncio
async def test_present_files_rejects_uploads_path(ctx: ToolContext) -> None:
    tool = PresentFilesTool()
    uploads_path = f"{vfs_config.uploads_prefix}photo.png"
    paths = get_paths()
    paths.ensure_conversation_dirs(ctx.user_id, ctx.conversation_id)
    (paths.sandbox_uploads_dir(ctx.user_id, ctx.conversation_id) / "photo.png").write_bytes(
        b"png"
    )

    result = await tool.execute({"filepaths": [uploads_path]}, ctx)

    assert result.is_error
    assert "Only virtual paths under" in result.content


@pytest.mark.asyncio
async def test_present_files_empty_list(ctx: ToolContext) -> None:
    tool = PresentFilesTool()
    result = await tool.execute({"filepaths": []}, ctx)

    assert result.is_error
    assert "filepaths is required" in result.content


@pytest.mark.asyncio
async def test_present_files_missing_file(ctx: ToolContext) -> None:
    tool = PresentFilesTool()
    missing = f"{vfs_config.outputs_prefix}missing.txt"
    get_paths().ensure_conversation_dirs(ctx.user_id, ctx.conversation_id)

    result = await tool.execute({"filepaths": [missing]}, ctx)

    assert result.is_error
    assert "File does not exist" in result.content


@pytest.mark.asyncio
async def test_present_files_path_traversal(ctx: ToolContext) -> None:
    tool = PresentFilesTool()
    get_paths().ensure_conversation_dirs(ctx.user_id, ctx.conversation_id)
    bad_path = f"{vfs_config.outputs_prefix}../workspace/secret.txt"

    result = await tool.execute({"filepaths": [bad_path]}, ctx)

    assert result.is_error
