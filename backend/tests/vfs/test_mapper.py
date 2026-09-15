"""Tests for physical -> virtual path mapping."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from app.vfs import paths as paths_module
from app.vfs.mapper import MappingContext, VirtualPathMapper
from app.vfs.paths import Paths


@pytest.fixture
def paths(tmp_path: Path) -> Generator[Paths, None, None]:
    instance = Paths(base_dir=tmp_path)
    paths_module._paths = instance
    yield instance
    paths_module._paths = None


def test_to_virtual_maps_workspace_file(paths: Paths) -> None:
    paths.ensure_conversation_dirs("user-1", "conv-1")
    work_dir = paths.sandbox_work_dir("user-1", "conv-1")
    target = work_dir / "notes.md"
    target.write_text("hi", encoding="utf-8")

    virtual = VirtualPathMapper().to_virtual(
        target, MappingContext(user_id="user-1", conversation_id="conv-1")
    )

    assert virtual == "/mnt/user-data/workspace/notes.md"


def test_to_virtual_does_not_map_sibling_with_shared_prefix(paths: Paths) -> None:
    """同级目录 "workspace_backup" 不能被当成 workspace 下的路径。

    旧实现用字符串前缀判定，会先命中 workspace 分支，随后
    ``relative_to(workspace_root)`` 抛 ValueError（未捕获）。
    """
    paths.ensure_conversation_dirs("user-1", "conv-1")
    sibling = paths.conversation_dir("user-1", "conv-1") / "workspace_backup"
    sibling.mkdir()
    target = sibling / "secret.md"
    target.write_text("secret", encoding="utf-8")

    virtual = VirtualPathMapper().to_virtual(
        target, MappingContext(user_id="user-1", conversation_id="conv-1")
    )

    assert virtual == str(target.resolve())
    assert not virtual.startswith("/mnt/user-data/workspace")
