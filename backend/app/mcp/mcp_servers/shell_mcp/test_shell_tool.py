"""Tests for ShellTool lazy initialization and executor caching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp.mcp_servers.shell_mcp.executor import ShellExecutor
from app.mcp.mcp_servers.shell_mcp.shell import ShellTool
from app.sandbox.executor import ExecutionResult
from app.schemas.config import SandboxConfig
from app.vfs.config import vfs_config


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
async def test_get_or_create_executor_missing_conversation_id(
    shell_tool: ShellTool,
) -> None:
    executor, error = await shell_tool.get_or_create_executor("user-1", "")
    assert executor is None
    assert error is not None
    assert "conversation_id" in error


@pytest.mark.asyncio
async def test_get_or_create_executor_initializes_once(shell_tool: ShellTool) -> None:
    workspace_path = Path("/tmp/test-workspace-shell")

    mock_paths = MagicMock()
    mock_paths.ensure_sandbox_work_dir.return_value = workspace_path

    with (
        patch(
            "app.mcp.mcp_servers.shell_mcp.shell.get_paths",
            return_value=mock_paths,
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

    def _ensure_work_dir(user_id: str, conversation_id: str) -> Path:
        if conversation_id == "ws-a":
            return path_a
        return path_b

    mock_paths = MagicMock()
    mock_paths.ensure_sandbox_work_dir.side_effect = _ensure_work_dir

    with (
        patch(
            "app.mcp.mcp_servers.shell_mcp.shell.get_paths",
            return_value=mock_paths,
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
    prefix = vfs_config.workspace_prefix.rstrip("/")
    adapted = executor._adapt_command_for_backend(
        f"cd {prefix} && npx --yes create-vite@latest vite-tmp"
    )
    assert adapted == "npx --yes create-vite@latest vite-tmp"


def test_adapt_command_strips_mkdir_workspace() -> None:
    executor = ShellExecutor()
    prefix = vfs_config.workspace_prefix.rstrip("/")
    adapted = executor._adapt_command_for_backend(
        f"mkdir -p {prefix} && cd {prefix} && ls"
    )
    assert adapted == "ls"


@pytest.mark.asyncio
async def test_get_or_create_executor_returns_error_when_docker_unavailable(
    shell_tool: ShellTool,
) -> None:
    workspace_path = Path("/tmp/test-workspace-docker-down")

    mock_paths = MagicMock()
    mock_paths.ensure_sandbox_work_dir.return_value = workspace_path

    mock_settings = MagicMock()
    mock_settings.sandbox = SandboxConfig(backend="docker", timeout=30000)
    with (
        patch(
            "app.mcp.mcp_servers.shell_mcp.shell.get_paths",
            return_value=mock_paths,
        ),
        patch("app.mcp.mcp_servers.shell_mcp.executor.settings", mock_settings),
        patch(
            "app.mcp.mcp_servers.shell_mcp.executor.is_docker_daemon_available",
            return_value=False,
        ),
    ):
        executor, error = await shell_tool.get_or_create_executor("user-1", "ws-1")

    assert executor is None
    assert error is not None
    assert "Docker daemon is unavailable" in error


@pytest.mark.asyncio
async def test_shell_executor_fails_when_docker_unavailable(
    tmp_path: Path,
) -> None:
    from app.mcp.mcp_servers.shell_mcp.executor import SandboxBackendError

    executor = ShellExecutor()

    mock_settings = MagicMock()
    mock_settings.sandbox = SandboxConfig(backend="docker", timeout=30000)
    with (
        patch("app.mcp.mcp_servers.shell_mcp.executor.settings", mock_settings),
        patch(
            "app.mcp.mcp_servers.shell_mcp.executor.is_docker_daemon_available",
            return_value=False,
        ),
        pytest.raises(SandboxBackendError, match="Docker daemon is unavailable"),
    ):
        await executor.initialize(tmp_path)


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
async def test_shell_executor_local_resolves_virtual_paths_in_command(
    tmp_path: Path,
) -> None:
    from app.vfs.paths import Paths

    paths = Paths(base_dir=tmp_path / "user_data")
    user_id = "user-1"
    conversation_id = "conv-1"
    paths.ensure_conversation_dirs(user_id, conversation_id)
    upload_file = paths.sandbox_uploads_dir(user_id, conversation_id) / "a.txt"
    upload_file.write_text("hi", encoding="utf-8")
    workspace = paths.ensure_sandbox_work_dir(user_id, conversation_id)

    executor = ShellExecutor()
    mock_backend = MagicMock()
    host_stdout = str(upload_file)
    mock_backend.execute = AsyncMock(
        return_value=ExecutionResult(stdout=host_stdout, return_code=0)
    )

    mock_settings = MagicMock()
    mock_settings.sandbox = SandboxConfig(backend="local", timeout=30000)
    with (
        patch("app.mcp.mcp_servers.shell_mcp.executor.settings", mock_settings),
        patch("app.mcp.mcp_servers.shell_mcp.shell.get_paths", return_value=paths),
        patch(
            "app.mcp.mcp_servers.shell_mcp.virtual_paths.get_paths", return_value=paths
        ),
        patch("app.vfs.paths.get_paths", return_value=paths),
        patch("app.vfs.mapper.get_paths", return_value=paths),
    ):
        await executor.initialize(
            workspace, user_id=user_id, conversation_id=conversation_id
        )
        executor._executor = mock_backend
        result = await executor.execute(command=f"cat {vfs_config.uploads_prefix}a.txt")

    call_args = mock_backend.execute.await_args
    assert call_args is not None
    request = call_args[0][0]
    assert vfs_config.uploads_prefix not in request.command
    assert str(upload_file) in request.command
    assert vfs_config.uploads_prefix in result.stdout
    assert "user_data" not in result.stdout


@pytest.mark.asyncio
async def test_shell_executor_local_sets_user_skills_dir_env(
    tmp_path: Path,
) -> None:
    from app.vfs.paths import Paths

    paths = Paths(base_dir=tmp_path / "user_data")
    user_id = "user-1"
    conversation_id = "conv-1"
    paths.ensure_conversation_dirs(user_id, conversation_id)
    paths.ensure_user_skills_dir(user_id)
    workspace = paths.ensure_sandbox_work_dir(user_id, conversation_id)
    expected_skills_dir = str(paths.user_skills_dir(user_id).resolve())

    executor = ShellExecutor()
    mock_backend = MagicMock()
    mock_backend.execute = AsyncMock(
        return_value=ExecutionResult(stdout="", return_code=0)
    )

    mock_settings = MagicMock()
    mock_settings.sandbox = SandboxConfig(backend="local", timeout=30000)
    with (
        patch("app.mcp.mcp_servers.shell_mcp.executor.settings", mock_settings),
        patch(
            "app.mcp.mcp_servers.shell_mcp.virtual_paths.get_paths", return_value=paths
        ),
        patch("app.vfs.paths.get_paths", return_value=paths),
    ):
        await executor.initialize(
            workspace, user_id=user_id, conversation_id=conversation_id
        )
        executor._executor = mock_backend
        await executor.execute(command="echo ok")

    call_args = mock_backend.execute.await_args
    assert call_args is not None
    request = call_args[0][0]
    assert request.env is not None
    assert request.env["USER_SKILLS_DIR"] == expected_skills_dir


@pytest.mark.asyncio
async def test_shell_executor_local_blocks_unsafe_host_path(tmp_path: Path) -> None:
    from app.vfs.paths import Paths

    paths = Paths(base_dir=tmp_path / "user_data")
    user_id = "user-1"
    conversation_id = "conv-1"
    paths.ensure_conversation_dirs(user_id, conversation_id)
    workspace = paths.ensure_sandbox_work_dir(user_id, conversation_id)

    executor = ShellExecutor()
    mock_backend = MagicMock()
    mock_backend.execute = AsyncMock(
        return_value=ExecutionResult(stdout="", return_code=0)
    )

    mock_settings = MagicMock()
    mock_settings.sandbox = SandboxConfig(backend="local", timeout=30000)
    with (
        patch("app.mcp.mcp_servers.shell_mcp.executor.settings", mock_settings),
        patch("app.mcp.mcp_servers.shell_mcp.shell.get_paths", return_value=paths),
        patch(
            "app.mcp.mcp_servers.shell_mcp.virtual_paths.get_paths", return_value=paths
        ),
        patch("app.vfs.paths.get_paths", return_value=paths),
    ):
        await executor.initialize(
            workspace, user_id=user_id, conversation_id=conversation_id
        )
        executor._executor = mock_backend
        result = await executor.execute(command="cat /Users/me/secret.txt")

    assert result.blocked is True
    assert result.block_reason is not None
    assert "Unsafe absolute paths" in result.block_reason
    mock_backend.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_shell_tool_blocks_rm_rf_without_executor(
    shell_tool: ShellTool,
) -> None:
    with patch.object(ShellExecutor, "execute", new_callable=AsyncMock) as mock_execute:
        output = await shell_tool.execute(
            {"command": "rm -rf /", "description": "dangerous test"},
            user_id="user-1",
            conversation_id="ws-1",
        )

    assert "Command blocked" in output
    mock_execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_shell_tool_warn_appends_to_output(
    shell_tool: ShellTool,
    tmp_path: Path,
) -> None:
    mock_paths = MagicMock()
    mock_paths.ensure_sandbox_work_dir.return_value = tmp_path

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(
        return_value=ExecutionResult(stdout="ok", return_code=0)
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
        output = await shell_tool.execute(
            {"command": "pip install requests", "description": "install deps"},
            user_id="user-1",
            conversation_id="ws-1",
        )

    assert "⚠️" in output
    assert "pip install requests" in output
    mock_executor.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_shell_tool_allows_vite_without_whitelist(
    shell_tool: ShellTool,
    tmp_path: Path,
) -> None:
    mock_paths = MagicMock()
    mock_paths.ensure_sandbox_work_dir.return_value = tmp_path

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(
        return_value=ExecutionResult(stdout="ok", return_code=0)
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
        output = await shell_tool.execute(
            {
                "command": "npx --yes create-vite@latest app",
                "description": "scaffold vite app",
            },
            user_id="user-1",
            conversation_id="ws-1",
        )

    assert "Command blocked" not in output
    mock_executor.execute.assert_awaited_once()


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
    assert request.cwd == vfs_config.workspace_prefix.rstrip("/")
