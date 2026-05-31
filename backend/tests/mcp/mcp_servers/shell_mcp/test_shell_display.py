"""Tests for shell structured display schema and shell tool payloads."""

from __future__ import annotations

from app.agents.utils.shell_result_processor import build_shell_display_items
from app.mcp.mcp_servers.shell_mcp.models import ShellToolExecuteResult
from app.mcp.mcp_servers.shell_mcp.shell import ShellTool
from app.sandbox.executor import ExecutionResult
from app.schemas.shell_display import ShellExecDisplayItem, ShellExecStructuredContent
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_shell_exec_structured_content_defaults() -> None:
    payload = ShellExecStructuredContent(exit_code=0)
    assert payload.stdout == ""
    assert payload.stderr == ""
    assert payload.blocked is False


def test_shell_exec_display_item_type() -> None:
    item = ShellExecDisplayItem.from_structured_content(
        {"exit_code": 1, "stderr": "fail"}
    )
    assert item.type == "shell_exec"
    assert item.exit_code == 1
    assert item.stderr == "fail"


def test_build_shell_display_items_wraps_single_entry() -> None:
    items = build_shell_display_items(
        ShellExecStructuredContent(
            exit_code=0,
            stdout="hello",
        ).model_dump(mode="json")
    )
    assert len(items) == 1
    assert items[0]["type"] == "shell_exec"
    assert items[0]["stdout"] == "hello"


@pytest.mark.asyncio
async def test_shell_tool_execute_returns_structured_content(tmp_path) -> None:
    shell_tool = ShellTool()
    mock_paths = MagicMock()
    mock_paths.sandbox_work_dir.return_value = tmp_path

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(
        return_value=ExecutionResult(
            stdout="ok",
            stderr="warn",
            return_code=2,
            duration_ms=12,
        )
    )

    with (
        patch(
            "app.mcp.mcp_servers.shell_mcp.shell.get_paths",
            return_value=mock_paths,
        ),
        patch.object(
            shell_tool,
            "get_or_create_executor",
            new_callable=AsyncMock,
            return_value=(mock_executor, None),
        ),
    ):
        result = await shell_tool.execute(
            {"command": "echo ok", "description": "print ok"},
            user_id="user-1",
            conversation_id="ws-1",
        )

    assert isinstance(result, ShellToolExecuteResult)
    assert "$ echo ok" in result.content
    assert result.structured_content is not None
    assert result.structured_content.exit_code == 2
    assert result.structured_content.stdout == "ok"
    assert result.structured_content.stderr == "warn"
    assert result.structured_content.duration_ms == 12

    display = build_shell_display_items(
        result.structured_content.model_dump(mode="json")
    )
    assert display[0]["type"] == "shell_exec"
