"""Tests for ToolUseBlock naming field validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.chat import ToolUseBlock


def test_tool_use_block_allows_name_only_for_unknown_tools() -> None:
    block = ToolUseBlock(id="cb_1", name="present_files")
    assert block.name == "present_files"
    assert block.server_name is None
    assert block.mcp_tool_name is None


def test_tool_use_block_requires_consistent_triple() -> None:
    block = ToolUseBlock(
        id="cb_1",
        name="file_present_files",
        server_name="file",
        mcp_tool_name="present_files",
    )
    assert block.name == "file_present_files"


def test_tool_use_block_rejects_partial_route() -> None:
    with pytest.raises(ValidationError, match="二者皆为空"):
        ToolUseBlock(id="cb_1", name="file_present_files", server_name="file")


def test_tool_use_block_rejects_mismatched_name() -> None:
    with pytest.raises(ValidationError, match="应为"):
        ToolUseBlock(
            id="cb_1",
            name="present_files",
            server_name="file",
            mcp_tool_name="present_files",
        )
