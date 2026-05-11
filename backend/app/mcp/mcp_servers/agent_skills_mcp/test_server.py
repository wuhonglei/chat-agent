from __future__ import annotations

import shutil
import uuid

import pytest

from app.mcp.mcp_servers.agent_skills_mcp.server import (
    clear_workspace,
    list_project_files,
    read_project_file,
    write_workspace_file,
)
from app.mcp.mcp_servers.agent_skills_mcp.utils import (
    get_skills_root,
    get_workspace_root,
    resolve_skills_path,
    resolve_workspace_path,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


@pytest.mark.asyncio
async def test_workspace_isolation_by_workspace_id() -> None:
    user_id = _new_id("user")
    workspace_a = _new_id("conv")
    workspace_b = _new_id("conv")
    path = "project/README.md"

    try:
        await write_workspace_file(
            user_id=user_id,
            workspace_id=workspace_a,
            path=path,
            content="workspace-a",
        )
        await write_workspace_file(
            user_id=user_id,
            workspace_id=workspace_b,
            path=path,
            content="workspace-b",
        )

        read_a = await read_project_file(
            user_id=user_id,
            workspace_id=workspace_a,
            scope="workspace",
            path=path,
        )
        read_b = await read_project_file(
            user_id=user_id,
            workspace_id=workspace_b,
            scope="workspace",
            path=path,
        )

        assert "workspace-a" in str(read_a.content)
        assert "workspace-b" in str(read_b.content)
    finally:
        await clear_workspace(user_id=user_id, workspace_id=workspace_a)
        await clear_workspace(user_id=user_id, workspace_id=workspace_b)
        shutil.rmtree(get_workspace_root(user_id, workspace_a), ignore_errors=True)
        shutil.rmtree(get_workspace_root(user_id, workspace_b), ignore_errors=True)


def test_resolve_workspace_path_rejects_invalid_workspace_id() -> None:
    with pytest.raises(ValueError, match="invalid workspace_id"):
        resolve_workspace_path("safe-user", "../escape", "a.txt")

    with pytest.raises(ValueError, match="invalid workspace_id"):
        resolve_workspace_path("safe-user", "", "a.txt")


def test_resolve_workspace_path_still_blocks_path_escape() -> None:
    with pytest.raises(ValueError, match="forbidden path"):
        resolve_workspace_path("safe-user", "safe-workspace", "../outside.txt")


@pytest.mark.asyncio
async def test_read_project_file_supports_skills_scope() -> None:
    root = get_skills_root()
    sample_file = root / "frontend-project-templates" / "SKILL.md"
    relative_path = str(sample_file.relative_to(root))
    result = await read_project_file(
        user_id="safe-user",
        workspace_id="safe-workspace",
        scope="skills",
        path=relative_path,
    )
    assert "name:" in str(result.content)


@pytest.mark.asyncio
async def test_list_project_files_supports_skills_scope() -> None:
    result = await list_project_files(
        user_id="safe-user",
        workspace_id="safe-workspace",
        scope="skills",
        path="",
    )
    payload = result.structured_content or {}
    items = payload.get("items", [])
    names = {item.get("name") for item in items if isinstance(item, dict)}
    assert "frontend-project-templates" in names


@pytest.mark.asyncio
async def test_list_project_files_depth_controls_recursion() -> None:
    user_id = _new_id("user")
    workspace_id = _new_id("conv")
    try:
        await write_workspace_file(
            user_id=user_id,
            workspace_id=workspace_id,
            path="project/README.md",
            content="root-readme",
        )
        await write_workspace_file(
            user_id=user_id,
            workspace_id=workspace_id,
            path="project/src/main.py",
            content="print('hello')",
        )

        depth1_result = await list_project_files(
            user_id=user_id,
            workspace_id=workspace_id,
            scope="workspace",
            path="project",
            depth=1,
        )
        depth1_items = (depth1_result.structured_content or {}).get("items", [])
        depth1_paths = {
            item.get("path") for item in depth1_items if isinstance(item, dict)
        }
        assert "src" in depth1_paths
        assert "src/main.py" not in depth1_paths

        depth2_result = await list_project_files(
            user_id=user_id,
            workspace_id=workspace_id,
            scope="workspace",
            path="project",
            depth=2,
        )
        depth2_items = (depth2_result.structured_content or {}).get("items", [])
        depth2_paths = {
            item.get("path") for item in depth2_items if isinstance(item, dict)
        }
        assert "src/main.py" in depth2_paths
    finally:
        await clear_workspace(user_id=user_id, workspace_id=workspace_id)
        shutil.rmtree(get_workspace_root(user_id, workspace_id), ignore_errors=True)


def test_resolve_skills_path_still_blocks_path_escape() -> None:
    with pytest.raises(ValueError, match="forbidden path"):
        resolve_skills_path("../outside.txt")
