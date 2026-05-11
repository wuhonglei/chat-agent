from __future__ import annotations

import shutil
import uuid

import pytest

from app.mcp.mcp_servers.agent_skills_mcp.server import (
    clear_workspace,
    read_workspace_file,
    write_workspace_file,
)
from app.mcp.mcp_servers.agent_skills_mcp.utils import (
    get_workspace_root,
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

        read_a = await read_workspace_file(
            user_id=user_id,
            workspace_id=workspace_a,
            path=path,
        )
        read_b = await read_workspace_file(
            user_id=user_id,
            workspace_id=workspace_b,
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
