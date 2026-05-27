"""Tests for skills virtual path resolution (public vs per-user custom)."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from app.vfs import paths as paths_module
from app.vfs.config import vfs_config
from app.vfs.paths import SKILLS_ROOT, Paths
from app.vfs.resolver import PathPermission, PathResolver


@pytest.fixture
def paths(tmp_path: Path) -> Generator[Paths, None, None]:
    instance = Paths(base_dir=tmp_path)
    paths_module._paths = instance
    yield instance
    paths_module._paths = None


@pytest.fixture
def resolver() -> PathResolver:
    return PathResolver()


def test_resolve_custom_skill_path(paths: Paths, resolver: PathResolver) -> None:
    custom_root = paths.ensure_user_skills_dir("user-1")
    physical, permission = resolver.resolve_virtual_to_physical(
        f"{vfs_config.skills_custom_prefix}my-skill/SKILL.md",
        "user-1",
        "conv-1",
    )
    assert permission == PathPermission.READ_WRITE
    assert physical == custom_root / "my-skill" / "SKILL.md"


def test_resolve_public_skill_path(resolver: PathResolver) -> None:
    physical, permission = resolver.resolve_virtual_to_physical(
        f"{vfs_config.skills_public_prefix}bootstrap/SKILL.md",
        "user-1",
        "conv-1",
    )
    assert permission == PathPermission.READ_ONLY
    assert physical == SKILLS_ROOT / "public" / "bootstrap" / "SKILL.md"


def test_custom_prefix_not_resolved_to_repo_skills_root(
    paths: Paths, resolver: PathResolver
) -> None:
    paths.ensure_user_skills_dir("user-1")
    physical, _ = resolver.resolve_virtual_to_physical(
        f"{vfs_config.skills_custom_prefix}my-skill/SKILL.md",
        "user-1",
        "conv-1",
    )
    assert not str(physical).startswith(str(SKILLS_ROOT.resolve()))


def test_resolve_custom_rejects_traversal(resolver: PathResolver) -> None:
    with pytest.raises(ValueError, match="Path traversal"):
        resolver.resolve_virtual_to_physical(
            f"{vfs_config.skills_custom_prefix}../escape.txt",
            "user-1",
            "conv-1",
        )
