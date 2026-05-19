"""Tests for ShellTool lazy initialization and executor caching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp.mcp_servers.shell_mcp.executor import ShellExecutor
from app.mcp.mcp_servers.shell_mcp.shell import ShellTool
from app.sandbox.executor import ExecutionResult
from app.schemas.config import SandboxConfig


@pytest.fixture
def shell_tool() -> ShellTool:
    return ShellTool()


@pytest.mark.asyncio
async def test_get_or_create_executor_missing_user_id(shell_tool: ShellTool) -> None:
    executor, error = await shell_tool.get_or_create_executor("", "ws-1")
    assert executor is None
    assert error is not None
    assert "user_id" in error


@pytest.mark.asyncio
async def test_get_or_create_executor_missing_workspace_id(
    shell_tool: ShellTool,
) -> None:
    executor, error = await shell_tool.get_or_create_executor("user-1", "")
    assert executor is None
    assert error is not None
    assert "workspace_id" in error


@pytest.mark.asyncio
async def test_get_or_create_executor_initializes_once(shell_tool: ShellTool) -> None:
    workspace_path = Path("/tmp/test-workspace-shell")

    with (
        patch(
            "app.mcp.mcp_servers.shell_mcp.shell.get_workspace_root",
            return_value=workspace_path,
        ),
        patch.object(
            ShellExecutor, "initialize", new_callable=AsyncMock
        ) as mock_initialize,
    ):
        mock_initialize.return_value = None

        executor1, err1 = await shell_tool.get_or_create_executor("user-1", "ws-1")
        executor2, err2 = await shell_tool.get_or_create_executor("user-1", "ws-1")

    assert err1 is None and err2 is None
    assert executor1 is not None and executor2 is not None
    assert executor1 is executor2
    mock_initialize.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_executor_different_workspaces(
    shell_tool: ShellTool,
) -> None:
    path_a = Path("/tmp/ws-a")
    path_b = Path("/tmp/ws-b")

    def _workspace_root(user_id: str, workspace_id: str) -> Path:
        if workspace_id == "ws-a":
            return path_a
        return path_b

    with (
        patch(
            "app.mcp.mcp_servers.shell_mcp.shell.get_workspace_root",
            side_effect=_workspace_root,
        ),
        patch.object(
            ShellExecutor, "initialize", new_callable=AsyncMock
        ) as mock_initialize,
    ):
        mock_initialize.return_value = None

        executor_a, _ = await shell_tool.get_or_create_executor("user-1", "ws-a")
        executor_b, _ = await shell_tool.get_or_create_executor("user-1", "ws-b")

    assert executor_a is not None and executor_b is not None
    assert executor_a is not executor_b
    assert mock_initialize.await_count == 2


def test_adapt_command_strips_cd_workspace() -> None:
    executor = ShellExecutor()
    adapted = executor._adapt_command_for_backend(
        "cd /workspace && npx --yes create-vite@latest vite-tmp"
    )
    assert adapted == "npx --yes create-vite@latest vite-tmp"


def test_adapt_command_strips_mkdir_workspace() -> None:
    executor = ShellExecutor()
    adapted = executor._adapt_command_for_backend(
        "mkdir -p /workspace && cd /workspace && ls"
    )
    assert adapted == "ls"


@pytest.mark.asyncio
async def test_shell_executor_falls_back_to_local_when_docker_unavailable(
    tmp_path: Path,
) -> None:
    executor = ShellExecutor()

    mock_settings = MagicMock()
    mock_settings.sandbox = SandboxConfig(backend="docker", timeout=30000)
    with (
        patch("app.mcp.mcp_servers.shell_mcp.executor.settings", mock_settings),
        patch(
            "app.mcp.mcp_servers.shell_mcp.executor.is_docker_daemon_available",
            return_value=False,
        ),
    ):
        await executor.initialize(tmp_path)

    assert executor._effective_backend == "local"


@pytest.mark.asyncio
async def test_shell_executor_local_cwd_uses_workspace_path(tmp_path: Path) -> None:
    executor = ShellExecutor()
    mock_backend = MagicMock()
    mock_backend.execute = AsyncMock(
        return_value=ExecutionResult(stdout="ok", return_code=0)
    )

    mock_settings = MagicMock()
    mock_settings.sandbox = SandboxConfig(backend="local", timeout=30000)
    with patch("app.mcp.mcp_servers.shell_mcp.executor.settings", mock_settings):
        await executor.initialize(tmp_path)
        executor._executor = mock_backend
        executor._initialized = True
        executor._workspace_path = tmp_path.resolve()
        executor._effective_backend = "local"

        await executor.execute(command="pwd")

    call_args = mock_backend.execute.await_args
    assert call_args is not None
    request = call_args[0][0]
    assert request.cwd == str(tmp_path.resolve())


@pytest.mark.asyncio
async def test_shell_executor_docker_cwd_uses_workspace_prefix(tmp_path: Path) -> None:
    executor = ShellExecutor()
    mock_backend = MagicMock()
    mock_backend.execute = AsyncMock(
        return_value=ExecutionResult(stdout="ok", return_code=0)
    )

    mock_settings = MagicMock()
    mock_settings.sandbox = SandboxConfig(backend="docker", timeout=30000)
    with (
        patch("app.mcp.mcp_servers.shell_mcp.executor.settings", mock_settings),
        patch(
            "app.mcp.mcp_servers.shell_mcp.executor.is_docker_daemon_available",
            return_value=True,
        ),
    ):
        await executor.initialize(tmp_path)
        executor._executor = mock_backend
        executor._initialized = True
        executor._workspace_path = tmp_path.resolve()
        executor._effective_backend = "docker"

        await executor.execute(command="ls")

    call_args = mock_backend.execute.await_args
    assert call_args is not None
    request = call_args[0][0]
    assert request.cwd == "/workspace"
