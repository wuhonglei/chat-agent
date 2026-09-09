"""Tests for local-sandbox virtual path translation inside Python scripts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.mcp.mcp_servers.shell_mcp.executor import ShellExecutor
from app.sandbox.local_vfs_shim.vfs_map import (
    load_mappings_from_env,
    rewrite_virtual_path,
    serialize_mappings,
)
from app.schemas.config import SandboxConfig
from app.vfs.paths import Paths


def test_rewrite_virtual_path_longest_prefix_wins() -> None:
    mappings = {
        "/mnt/user-data": "/host/conv",
        "/mnt/user-data/workspace": "/host/conv/workspace",
    }
    result = rewrite_virtual_path("/mnt/user-data/workspace/ai-hot-chart.png", mappings)
    assert result == "/host/conv/workspace/ai-hot-chart.png"


def test_rewrite_virtual_path_leaves_unrelated_paths() -> None:
    mappings = {"/mnt/user-data/workspace": "/host/workspace"}
    assert rewrite_virtual_path("/tmp/foo", mappings) == "/tmp/foo"
    assert rewrite_virtual_path(3, mappings) == 3


def test_serialize_and_load_mappings_roundtrip() -> None:
    mappings = {
        "/mnt/user-data": "/host/conv",
        "/mnt/user-data/workspace": "/host/conv/workspace",
    }
    loaded = load_mappings_from_env(serialize_mappings(mappings))
    keys = list(loaded)
    assert keys[0] == "/mnt/user-data/workspace"
    assert loaded["/mnt/user-data/workspace"] == "/host/conv/workspace"


@pytest.mark.asyncio
async def test_local_python_script_open_virtual_workspace_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduce FileNotFoundError from scripts that open /mnt/user-data/..."""
    paths = Paths(base_dir=tmp_path / "user_data")
    user_id = "user-1"
    conversation_id = "conv-1"
    paths.ensure_conversation_dirs(user_id, conversation_id)
    workspace = paths.ensure_sandbox_work_dir(user_id, conversation_id)
    (workspace / "ai-hot-chart.png").write_bytes(b"PNGDATA")
    (workspace / "build_surprise.py").write_text(
        "with open('/mnt/user-data/workspace/ai-hot-chart.png', 'rb') as f:\n"
        "    print(f.read().decode())\n",
        encoding="utf-8",
    )

    from app.vfs import paths as paths_module

    monkeypatch.setattr(paths_module, "_paths", paths)
    mock_settings = type("Settings", (), {"sandbox": SandboxConfig(backend="local")})()

    with (
        patch(
            "app.mcp.mcp_servers.shell_mcp.executor.settings",
            mock_settings,
        ),
        patch(
            "app.mcp.mcp_servers.shell_mcp.virtual_paths.get_paths",
            return_value=paths,
        ),
        patch("app.vfs.paths.get_paths", return_value=paths),
        patch("app.vfs.mapper.get_paths", return_value=paths),
    ):
        executor = ShellExecutor()
        await executor.initialize(
            workspace, user_id=user_id, conversation_id=conversation_id
        )
        result = await executor.execute(
            command="python3 /mnt/user-data/workspace/build_surprise.py",
            description="read chart via virtual path",
        )
        await executor.cleanup()

    assert result.return_code == 0, result.stderr
    assert result.stdout.strip() == "PNGDATA"


@pytest.mark.asyncio
async def test_local_python_chdir_virtual_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = Paths(base_dir=tmp_path / "user_data")
    user_id = "user-1"
    conversation_id = "conv-1"
    paths.ensure_conversation_dirs(user_id, conversation_id)
    workspace = paths.ensure_sandbox_work_dir(user_id, conversation_id)
    (workspace / "chart_b64.txt").write_text("abc123", encoding="utf-8")
    (workspace / "build_surprise.py").write_text(
        "import os\n"
        "os.chdir('/mnt/user-data/workspace')\n"
        "with open('chart_b64.txt', 'r') as f:\n"
        "    print(f.read())\n",
        encoding="utf-8",
    )

    from app.vfs import paths as paths_module

    monkeypatch.setattr(paths_module, "_paths", paths)
    mock_settings = type("Settings", (), {"sandbox": SandboxConfig(backend="local")})()

    with (
        patch(
            "app.mcp.mcp_servers.shell_mcp.executor.settings",
            mock_settings,
        ),
        patch(
            "app.mcp.mcp_servers.shell_mcp.virtual_paths.get_paths",
            return_value=paths,
        ),
        patch("app.vfs.paths.get_paths", return_value=paths),
        patch("app.vfs.mapper.get_paths", return_value=paths),
    ):
        executor = ShellExecutor()
        await executor.initialize(
            workspace, user_id=user_id, conversation_id=conversation_id
        )
        result = await executor.execute(
            command="python3 /mnt/user-data/workspace/build_surprise.py",
            description="chdir then read relative file",
        )
        await executor.cleanup()

    assert result.return_code == 0, result.stderr
    assert result.stdout.strip() == "abc123"
