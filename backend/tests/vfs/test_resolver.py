"""Tests for shared relative path resolution."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from app.vfs import paths as paths_module
from app.vfs.config import vfs_config
from app.vfs.paths import Paths
from app.vfs.resolver import PathResolver, resolve_relative_under_root


@pytest.fixture
def paths(tmp_path: Path) -> Generator[Paths, None, None]:
    instance = Paths(base_dir=tmp_path)
    paths_module._paths = instance
    yield instance
    paths_module._paths = None


def test_resolve_relative_under_root_rejects_traversal(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    with pytest.raises(ValueError, match="forbidden path"):
        resolve_relative_under_root(root, "../outside.txt")


def test_resolve_relative_under_root_rejects_sibling_with_shared_prefix(
    tmp_path: Path,
) -> None:
    """ "c1_backup" 与 root "c1" 共享字符串前缀，但不在 root 之下。

    旧的字符串前缀判定（``str(target).startswith(str(root))``）会放行，
    只要 root 里有一条指向该同级目录的软链即可读到 root 之外的内容。
    """
    conversation = tmp_path / "conversations"
    root = conversation / "c1"
    root.mkdir(parents=True)
    sibling = conversation / "c1_backup"
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret", encoding="utf-8")
    assert str(sibling).startswith(str(root))  # 前缀确实共享，测试的是判定方式

    (root / "leak").symlink_to(sibling)

    with pytest.raises(ValueError, match="path escapes workspace"):
        resolve_relative_under_root(root, "leak/secret.txt")


def test_resolver_rejects_symlink_to_sibling_with_shared_prefix(
    paths: Paths,
) -> None:
    """虚拟路径解析同样不能靠字符串前缀放行指向同级目录的软链。"""
    paths.ensure_conversation_dirs("user-1", "conv-1")
    work_dir = paths.sandbox_work_dir("user-1", "conv-1")
    sibling = paths.conversation_dir("user-1", "conv-1") / "workspace_backup"
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret", encoding="utf-8")
    (work_dir / "leak").symlink_to(sibling)

    with pytest.raises(ValueError, match="Path traversal detected"):
        PathResolver().resolve_virtual_to_physical(
            f"{vfs_config.workspace_prefix}leak/secret.txt",
            "user-1",
            "conv-1",
        )
